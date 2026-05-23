"""Intent classification using gpt-4o-mini."""

import json
import re
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from config import get_settings
from utils.logging_utils import log_event
from utils.token_tracker import token_tracker

settings = get_settings()

INTENTS = [
    "GENERAL_QUESTION",
    "ACCOUNT_ISSUE",
    "CARD_ISSUE",
    "TRANSFER_ISSUE",
    "LOAN_ISSUE",
    "COMPLAINT",
    "GREETING",
    "UNCLEAR",
]

SYSTEM_PROMPT = f"""Classify AccessBank customer messages into exactly one intent:
{', '.join(INTENTS)}

Rules:
- Working hours, contact info, branch, products → GENERAL_QUESTION
- Salam, hello, hi → GREETING
- Blocked/lost card, card payment → CARD_ISSUE
- Failed transfer, money deducted → TRANSFER_ISSUE
- Loan status, repayment → LOAN_ISSUE
- Account access, login → ACCOUNT_ISSUE
- Service complaint → COMPLAINT
- Vague message → UNCLEAR

Return JSON: {{"intent": "...", "confidence": 0.0-1.0}}"""


@dataclass
class IntentResult:
    intent: str
    confidence: float


def _rule_based_intent(text: str) -> IntentResult:
    lower = text.lower()
    if re.search(r"\b(salam|hello|hi|привет|günaydın)\b", lower):
        return IntentResult("GREETING", 0.9)
    if re.search(
        r"iş saat|working hour|filial|branch|151|whatsapp|contact",
        lower,
    ):
        return IntentResult("GENERAL_QUESTION", 0.85)
    if re.search(r"kart|card|blok|block|cvv", lower):
        return IntentResult("CARD_ISSUE", 0.85)
    if re.search(r"köçürm|transfer|uğursuz|pul.*getdi|payment", lower):
        return IntentResult("TRANSFER_ISSUE", 0.85)
    if re.search(r"kredit|loan|borc", lower):
        return IntentResult("LOAN_ISSUE", 0.8)
    if re.search(r"şikayət|complaint|narazı", lower):
        return IntentResult("COMPLAINT", 0.8)
    if re.search(r"hesab|account|login|otp|şifrə", lower):
        return IntentResult("ACCOUNT_ISSUE", 0.8)
    if re.search(r"case\s*#?\s*\d+", lower, re.I):
        return IntentResult("GENERAL_QUESTION", 0.7)
    if len(text.strip()) < 8:
        return IntentResult("UNCLEAR", 0.6)
    return IntentResult("GENERAL_QUESTION", 0.5)


def classify_intent(text: str) -> IntentResult:
    if not settings.openai_api_key:
        result = _rule_based_intent(text)
        log_event("intent_classified", intent=result.intent, confidence=result.confidence)
        return result

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=80,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text[:1500]},
            ],
            response_format={"type": "json_object"},
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

        data = json.loads(response.choices[0].message.content or "{}")
        intent = str(data.get("intent", "UNCLEAR")).upper()
        if intent not in INTENTS:
            intent = "UNCLEAR"
        confidence = float(data.get("confidence", 0.7))
        log_event("intent_classified", intent=intent, confidence=round(confidence, 2))
        return IntentResult(intent, confidence)
    except Exception as e:
        log_event("intent_error", error=str(e)[:100])
        return _rule_based_intent(text)
