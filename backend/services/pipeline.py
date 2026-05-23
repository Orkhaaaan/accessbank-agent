"""Main message processing pipeline."""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.department_router import route_department
from agents.intent_classifier import classify_intent
from agents.knowledge_agent import (
    answer_from_knowledge,
    get_clarifying_question,
    get_greeting,
)
from agents.sentiment_analyzer import analyze_sentiment
from models.case import Channel
from models.message import MessageRole
from services.case_service import CaseService
from services.email_service import EmailService
from utils.logging_utils import log_event
from utils.security import (
    detect_language,
    detect_sensitive_data,
    get_refusal_message,
    sanitize_input,
)

ESCALATION_INTENTS = {
    "ACCOUNT_ISSUE",
    "CARD_ISSUE",
    "TRANSFER_ISSUE",
    "LOAN_ISSUE",
    "COMPLAINT",
}

COLLECT_FIELDS = ["name", "phone", "description", "incident_datetime"]

PROMPTS = {
    "az": {
        "name": "Zəhmət olmasa adınızı və soyadınızı yazın.",
        "phone": "Əlaqə nömrənizi yazın (+994...).",
        "description": "Probleminizi qısa təsvir edin.",
        "incident_datetime": "Hadisə tarixi və vaxtını yazın (məs: 20.05.2026, 14:30).",
        "case_created": "Müraciətiniz qeydə alındı. Case #{case_id} — {department}. Status: {status}",
        "case_status": "Case #{case_id} statusu: {status}. Şöbə: {department}.",
        "case_not_found": "Case #{case_id} tapılmadı.",
    },
    "ru": {
        "name": "Укажите ваше имя и фамилию.",
        "phone": "Укажите номер телефона (+994...).",
        "description": "Кратко опишите проблему.",
        "incident_datetime": "Укажите дату и время инцидента.",
        "case_created": "Обращение зарегистрировано. Case #{case_id} — {department}. Статус: {status}",
        "case_status": "Case #{case_id}: статус {status}. Отдел: {department}.",
        "case_not_found": "Case #{case_id} не найден.",
    },
    "en": {
        "name": "Please provide your full name.",
        "phone": "Please provide your phone number (+994...).",
        "description": "Briefly describe your issue.",
        "incident_datetime": "Please provide the date and time of the incident.",
        "case_created": "Your request was registered. Case #{case_id} — {department}. Status: {status}",
        "case_status": "Case #{case_id} status: {status}. Department: {department}.",
        "case_not_found": "Case #{case_id} not found.",
    },
}


@dataclass
class SessionState:
    session_id: str
    language: str = "az"
    collecting: bool = False
    collect_step: int = 0
    collect_data: Dict[str, str] = field(default_factory=dict)
    pending_intent: Optional[str] = None
    last_sentiment: Optional[Any] = None
    channel: str = "WEB"


# In-memory session store (use Redis in production)
_sessions: Dict[str, SessionState] = {}


def get_session(session_id: str, channel: str = "WEB") -> SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = SessionState(session_id=session_id, channel=channel)
    return _sessions[session_id]


@dataclass
class PipelineResponse:
    reply: str
    session_id: str
    transcribed_text: Optional[str] = None
    sentiment: Optional[str] = None
    emotion: Optional[str] = None
    urgency_score: Optional[int] = None
    is_critical: bool = False
    intent: Optional[str] = None
    case_id: Optional[str] = None
    department: Optional[str] = None
    requires_confirmation: bool = False


class MessagePipeline:
    def __init__(
        self,
        case_service: CaseService,
        email_service: EmailService,
        telegram_alert=None,
    ):
        self.cases = case_service
        self.email = email_service
        self.telegram_alert = telegram_alert

    def _prompt(self, lang: str, key: str, **kwargs) -> str:
        p = PROMPTS.get(lang[:2], PROMPTS["az"])
        return p.get(key, "").format(**kwargs)

    def process(
        self,
        text: str,
        session_id: str,
        channel: Channel = Channel.WEB,
        skip_collection: bool = False,
    ) -> PipelineResponse:
        text = sanitize_input(text)
        session = get_session(session_id, channel.value)
        lang = detect_language(text) if not session.language else session.language
        if len(text) > 20:
            session.language = lang

        log_event(
            "message_received",
            channel=channel.value,
            type="text",
            length=len(text),
        )

        # Sensitive data check
        sensitive = detect_sensitive_data(text)
        if sensitive:
            refusal = get_refusal_message(lang)
            self.cases.save_message(
                session_id, MessageRole.USER, text, channel=channel.value
            )
            self.cases.save_message(
                session_id,
                MessageRole.ASSISTANT,
                refusal,
                channel=channel.value,
            )
            # Continue helping after refusal
            follow_up = {
                "az": " Probleminizi təsvir edin — PIN və ya kart məlumatı olmadan kömək edə bilərəm.",
                "ru": " Опишите проблему — мы поможем без конфиденциальных данных.",
                "en": " Describe your issue — we can help without sensitive data.",
            }
            reply = refusal + follow_up.get(lang[:2], follow_up["az"])
            return PipelineResponse(reply=reply, session_id=session_id)

        # Case status query
        case_id_query = CaseService.parse_case_status_query(text)
        if case_id_query:
            case = self.cases.get_case(case_id_query)
            if case:
                status_val = case.status.value if hasattr(case.status, "value") else str(case.status)
                reply = self._prompt(
                    lang,
                    "case_status",
                    case_id=case.case_id,
                    status=status_val,
                    department=case.department,
                )
            else:
                reply = self._prompt(lang, "case_not_found", case_id=case_id_query)
            return PipelineResponse(
                reply=reply,
                session_id=session_id,
                case_id=case_id_query,
            )

        # Continue collection flow
        if session.collecting and not skip_collection:
            return self._handle_collection(text, session, channel)

        sentiment = analyze_sentiment(text)
        session.last_sentiment = sentiment
        intent = classify_intent(text)

        self.cases.save_message(
            session_id,
            MessageRole.USER,
            text,
            channel=channel.value,
            sentiment=sentiment.sentiment,
            emotion=sentiment.emotion,
            intent=intent.intent,
        )

        if intent.intent == "GREETING":
            reply = get_greeting(lang)
            self.cases.save_message(
                session_id, MessageRole.ASSISTANT, reply, channel=channel.value
            )
            return PipelineResponse(
                reply=reply,
                session_id=session_id,
                sentiment=sentiment.sentiment,
                emotion=sentiment.emotion,
                urgency_score=sentiment.urgency_score,
                intent=intent.intent,
            )

        if intent.intent == "UNCLEAR":
            reply = get_clarifying_question(lang)
            self.cases.save_message(
                session_id, MessageRole.ASSISTANT, reply, channel=channel.value
            )
            return PipelineResponse(
                reply=reply,
                session_id=session_id,
                intent=intent.intent,
            )

        if intent.intent == "GENERAL_QUESTION":
            reply = answer_from_knowledge(
                text, lang, sentiment_emotion=sentiment.emotion
            )
            self.cases.save_message(
                session_id, MessageRole.ASSISTANT, reply, channel=channel.value
            )
            return PipelineResponse(
                reply=reply,
                session_id=session_id,
                sentiment=sentiment.sentiment,
                emotion=sentiment.emotion,
                urgency_score=sentiment.urgency_score,
                is_critical=sentiment.is_critical,
                intent=intent.intent,
            )

        if intent.intent in ESCALATION_INTENTS:
            session.collecting = True
            session.collect_step = 0
            session.pending_intent = intent.intent
            session.collect_data = {"issue_preview": text[:500]}
            reply = self._prompt(lang, COLLECT_FIELDS[0])
            self.cases.save_message(
                session_id, MessageRole.ASSISTANT, reply, channel=channel.value
            )
            return PipelineResponse(
                reply=reply,
                session_id=session_id,
                sentiment=sentiment.sentiment,
                emotion=sentiment.emotion,
                urgency_score=sentiment.urgency_score,
                is_critical=sentiment.is_critical,
                intent=intent.intent,
            )

        reply = get_clarifying_question(lang)
        return PipelineResponse(reply=reply, session_id=session_id, intent=intent.intent)

    def _handle_collection(
        self, text: str, session: SessionState, channel: Channel
    ) -> PipelineResponse:
        lang = session.language
        field = COLLECT_FIELDS[session.collect_step]
        session.collect_data[field] = text
        session.collect_step += 1

        if session.collect_step < len(COLLECT_FIELDS):
            next_field = COLLECT_FIELDS[session.collect_step]
            reply = self._prompt(lang, next_field)
            self.cases.save_message(
                session.session_id,
                MessageRole.ASSISTANT,
                reply,
                channel=channel.value,
            )
            return PipelineResponse(reply=reply, session_id=session.session_id)

        return self._finalize_case(session, channel)

    def _finalize_case(
        self, session: SessionState, channel: Channel
    ) -> PipelineResponse:
        data = session.collect_data
        issue = data.get("description") or data.get("issue_preview", "")
        from agents.intent_classifier import IntentResult

        intent = IntentResult(
            session.pending_intent or "COMPLAINT", 0.9
        )
        combined_text = f"{issue} {data.get('issue_preview', '')}"
        sentiment = session.last_sentiment or analyze_sentiment(combined_text)
        routing = route_department(combined_text, intent, sentiment)

        case = self.cases.create_case(
            customer_name=data.get("name", ""),
            customer_phone=data.get("phone", ""),
            issue_description=issue,
            department=routing.department,
            routing_reason=routing.reason,
            channel=channel,
            sentiment=sentiment.sentiment,
            emotion=sentiment.emotion,
            urgency_score=sentiment.urgency_score,
            is_critical=sentiment.is_critical,
            intent=intent.intent,
            incident_datetime=data.get("incident_datetime"),
            language=session.language,
        )

        sent, thread_id = self.email.send_escalation(case)
        if sent or thread_id:
            self.cases.update_email_status(case.case_id, thread_id, sent)

        if sentiment.is_critical and self.telegram_alert:
            self.telegram_alert.send_critical_alert(case)
            log_event(
                "critical_alert_triggered",
                case_id=case.case_id,
                reason=f"urgency={sentiment.urgency_score}, emotion={sentiment.emotion}",
            )

        status_val = case.status.value if hasattr(case.status, "value") else "OPEN"
        reply = self._prompt(
            session.language,
            "case_created",
            case_id=case.case_id,
            department=case.department,
            status=status_val,
        )

        self.cases.save_message(
            session.session_id,
            MessageRole.ASSISTANT,
            reply,
            case_id=case.case_id,
            channel=channel.value,
        )

        session.collecting = False
        session.collect_step = 0
        session.collect_data = {}

        return PipelineResponse(
            reply=reply,
            session_id=session.session_id,
            case_id=case.case_id,
            department=case.department,
            sentiment=sentiment.sentiment,
            emotion=sentiment.emotion,
            urgency_score=sentiment.urgency_score,
            is_critical=sentiment.is_critical,
            intent=intent.intent,
        )
