"""Official email escalation via Gmail API or Microsoft Graph."""

import base64
import uuid
from email.mime.text import MIMEText
from typing import Optional, Tuple

import httpx

from config import get_settings
from models.case import Case
from utils.logging_utils import log_event

settings = get_settings()


class EmailService:
    def __init__(self) -> None:
        self._gmail_token: Optional[str] = None

    def _get_gmail_access_token(self) -> Optional[str]:
        if not settings.use_gmail:
            return None
        try:
            resp = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "refresh_token": settings.gmail_refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as e:
            log_event("email_token_error", provider="gmail", error=str(e)[:80])
            return None

    def _get_ms_access_token(self) -> Optional[str]:
        if not settings.use_microsoft:
            return None
        try:
            url = (
                f"https://login.microsoftonline.com/{settings.ms_tenant_id}"
                "/oauth2/v2.0/token"
            )
            resp = httpx.post(
                url,
                data={
                    "client_id": settings.ms_client_id,
                    "client_secret": settings.ms_client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as e:
            log_event("email_token_error", provider="microsoft", error=str(e)[:80])
            return None

    def _build_subject(self, case: Case) -> str:
        prefix = "⚠️ " if case.is_critical else ""
        critical_tag = " — CRITICAL" if case.is_critical else ""
        return (
            f"{prefix}[AccessBank Support] Case #{case.case_id} — "
            f"{case.department}{critical_tag}"
        )

    def _build_body(self, case: Case) -> str:
        return f"""
AccessBank Support Case Escalation
==================================
Case ID: {case.case_id}
Department: {case.department}
Routing reason: {case.routing_reason or 'N/A'}
Status: {case.status.value if hasattr(case.status, 'value') else case.status}
Channel: {case.channel.value if hasattr(case.channel, 'value') else case.channel}

Customer: {case.customer_name or 'N/A'}
Phone (masked): {case.customer_phone or 'N/A'}
Incident date/time: {case.incident_datetime or 'N/A'}

Issue:
{case.issue_description or 'N/A'}

Sentiment: {case.sentiment or 'N/A'}
Emotion: {case.emotion or 'N/A'}
Urgency: {case.urgency_score}/5
Critical: {'YES' if case.is_critical else 'No'}

---
This is an automated escalation from AccessBank AI Support Agent.
"""

    def send_escalation(self, case: Case) -> Tuple[bool, str]:
        if settings.skip_email:
            thread_id = f"mock-{uuid.uuid4().hex[:12]}"
            log_event("email_skipped", case_id=case.case_id, reason="skip_email")
            return True, thread_id

        subject = self._build_subject(case)
        body = self._build_body(case)
        to_email = settings.escalation_email

        if settings.use_gmail:
            return self._send_gmail(subject, body, to_email, case.case_id)
        if settings.use_microsoft:
            return self._send_microsoft(subject, body, to_email, case.case_id)

        thread_id = f"dev-{uuid.uuid4().hex[:12]}"
        log_event(
            "email_not_configured",
            case_id=case.case_id,
            thread_id=thread_id,
        )
        return False, thread_id

    def _send_gmail(
        self, subject: str, body: str, to_email: str, case_id: str
    ) -> Tuple[bool, str]:
        token = self._get_gmail_access_token()
        if not token:
            return False, ""

        sender = settings.gmail_sender_email or settings.escalation_email
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to_email
        message["from"] = sender
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            resp = httpx.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"raw": raw},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            thread_id = data.get("threadId", data.get("id", ""))
            log_event("email_sent", case_id=case_id, thread_id=thread_id[:20])
            return True, thread_id
        except Exception as e:
            log_event("email_send_error", case_id=case_id, error=str(e)[:80])
            return False, ""

    def _send_microsoft(
        self, subject: str, body: str, to_email: str, case_id: str
    ) -> Tuple[bool, str]:
        token = self._get_ms_access_token()
        if not token:
            return False, ""

        sender = settings.ms_sender_email
        if not sender:
            log_event("email_config_error", error="ms_sender_email missing")
            return False, ""

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            },
            "saveToSentItems": True,
        }
        try:
            resp = httpx.post(
                f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            thread_id = f"ms-{uuid.uuid4().hex[:12]}"
            log_event("email_sent", case_id=case_id, thread_id=thread_id[:20])
            return True, thread_id
        except Exception as e:
            log_event("email_send_error", case_id=case_id, error=str(e)[:80])
            return False, ""
