"""Structured logging — never log sensitive data."""

import logging
import re
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("accessbank.agent")

SENSITIVE_PATTERNS = [
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CARD]"),
    (re.compile(r"\b\d{3,4}\b"), "[NUM]"),
    (re.compile(r"pin\s*[:=]?\s*\d+", re.I), "[PIN]"),
    (re.compile(r"otp\s*[:=]?\s*\d+", re.I), "[OTP]"),
    (re.compile(r"cvv|cvc", re.I), "[CVV]"),
    (re.compile(r"\+994\d{9}"), "[PHONE]"),
    (re.compile(r"\d{10,}"), "[PHONE]"),
]


def sanitize_for_log(text: str) -> str:
    if not text:
        return ""
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result[:200]


def mask_phone(phone: str) -> str:
    """Mask phone for storage: ***-**-XX (last 2 digits visible)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 2:
        return "***-**-??"
    return f"***-**-{digits[-2:]}"


def log_event(event: str, **kwargs) -> None:
    safe_kwargs = {
        k: sanitize_for_log(str(v)) if isinstance(v, str) else v
        for k, v in kwargs.items()
    }
    safe_kwargs["timestamp"] = datetime.utcnow().isoformat()
    parts = " | ".join(f"{k}={v}" for k, v in safe_kwargs.items())
    logger.info(f"{event} | {parts}")
