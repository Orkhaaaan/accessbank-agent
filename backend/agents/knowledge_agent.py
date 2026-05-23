"""Knowledge agent — answers GENERAL_QUESTION via RAG."""

from typing import Optional

from openai import OpenAI

from config import get_settings
from services.rag_service import get_rag_service
from utils.logging_utils import log_event
from utils.token_tracker import token_tracker

settings = get_settings()
MAX_TOKENS = 500

GREETINGS = {
    "az": (
        "Salam! AccessBank müştəri dəstəyinə xoş gəlmisiniz. "
        "Sizə necə kömək edə bilərəm?"
    ),
    "ru": (
        "Здравствуйте! Добро пожаловать в службу поддержки AccessBank. "
        "Чем могу помочь?"
    ),
    "en": (
        "Hello! Welcome to AccessBank customer support. "
        "How can I help you today?"
    ),
}

CLARIFY = {
    "az": "Zəhmət olmasa probleminizi bir az daha ətraflı izah edin.",
    "ru": "Пожалуйста, опишите вашу проблему немного подробнее.",
    "en": "Could you please describe your issue in a bit more detail?",
}


def get_greeting(language: str) -> str:
    return GREETINGS.get(language[:2], GREETINGS["az"])


def get_clarifying_question(language: str) -> str:
    return CLARIFY.get(language[:2], CLARIFY["az"])


def answer_from_knowledge(
    question: str,
    language: str = "az",
    sentiment_emotion: Optional[str] = None,
) -> str:
    rag = get_rag_service()
    chunks, tokens_used = rag.retrieve(question, top_k=3)

    log_event(
        "rag_retrieval",
        chunks_returned=len(chunks),
        tokens_used=tokens_used,
    )

    context = "\n\n---\n\n".join(chunks[:3])
    if not context:
        context = "AccessBank: call 151, WhatsApp +994554400151, support@accessbank.az"

    if not settings.openai_api_key:
        return _fallback_answer(context, language)

    tone = ""
    if sentiment_emotion in ("ANGRY", "URGENT", "FRUSTRATED"):
        tone = "Be extra empathetic and concise. Prioritize reassurance."

    lang_instruction = {
        "az": "Respond in Azerbaijani.",
        "ru": "Respond in Russian.",
        "en": "Respond in English.",
    }.get(language[:2], "Respond in Azerbaijani.")

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=400,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are AccessBank Azerbaijan support assistant. {lang_instruction} "
                        f"Use ONLY the context below. Be professional, warm, concise. "
                        f"Never ask for PIN, CVV, OTP, or full card number. {tone}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context[:900]}\n\nQuestion: {question[:500]}",
                },
            ],
        )
        usage = response.usage
        if usage:
            cost = token_tracker.record(
                "gpt-4o-mini",
                usage.prompt_tokens,
                usage.completion_tokens,
            )
            log_event(
                "token_usage",
                model="gpt-4o-mini",
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_estimate=round(cost, 6),
            )
        return response.choices[0].message.content or _fallback_answer(context, language)
    except Exception as e:
        log_event("knowledge_agent_error", error=str(e)[:100])
        return _fallback_answer(context, language)


def _fallback_answer(context: str, language: str) -> str:
    if language.startswith("ru"):
        return f"На основе информации AccessBank:\n{context[:600]}"
    if language.startswith("en"):
        return f"Based on AccessBank information:\n{context[:600]}"
    return f"AccessBank məlumatına əsasən:\n{context[:600]}"
