"""Security: sensitive data detection and input sanitization."""

import re
from html import escape
from typing import Optional, Tuple

SENSITIVE_PATTERNS = [
    (re.compile(r"\bpin\s*(?:kodu?m?|code)?\s*[:=]?\s*\d{3,8}", re.I), "PIN"),
    (re.compile(r"pin\s*kod\w*\s*\d{3,8}", re.I), "PIN"),
    (re.compile(r"\b\d{3,4}\s*(?:cvv|cvc)\b|\b(?:cvv|cvc)\s*[:=]?\s*\d{3,4}\b", re.I), "CVV"),
    (re.compile(r"\b(?:şifrə|parol|password)\s*[:=]?\s*\S+", re.I), "PASSWORD"),
    (re.compile(r"\botp\s*[:=]?\s*\d{4,8}\b", re.I), "OTP"),
    (re.compile(r"\b\d{16}\b"), "FULL_CARD"),
    (re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}\b"), "FULL_CARD"),
]

REFUSAL_AZ = (
    "Təhlükəsizlik səbəbindən bu məlumatı paylaşmayın. "
    "Bu məlumat bank tərəfindən heç vaxt tələb olunmur."
)
REFUSAL_RU = (
    "В целях безопасности не делитесь этой информацией. "
    "Банк никогда не запрашивает такие данные."
)
REFUSAL_EN = (
    "For security reasons, please do not share this information. "
    "The bank never requests such data."
)


def detect_sensitive_data(text: str) -> Optional[str]:
    """Return sensitive type if detected, else None."""
    for pattern, sensitive_type in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return sensitive_type
    return None


def get_refusal_message(language: str = "az") -> str:
    if language.startswith("ru"):
        return REFUSAL_RU
    if language.startswith("en"):
        return REFUSAL_EN
    return REFUSAL_AZ


def sanitize_input(text: str, max_length: int = 4000) -> str:
    if not text:
        return ""
    cleaned = escape(text.strip())
    return cleaned[:max_length]


def detect_language(text: str) -> str:
    """Simple heuristic language detection."""
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    if re.search(
        r"\b(the|is|are|hello|help|card|transfer)\b", text, re.I
    ):
        return "en"
    az_chars = re.search(r"[əğıöüşçƏĞIÖÜŞÇ]", text, re.I)
    az_words = re.search(
        r"\b(salam|kart|köçürmə|müraciət|iş saat|bank)\b", text, re.I
    )
    if az_chars or az_words:
        return "az"
    return "az"
