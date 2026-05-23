"""Route cases to one of five AccessBank departments."""

from dataclasses import dataclass
from typing import Optional

from agents.intent_classifier import IntentResult
from agents.sentiment_analyzer import SentimentResult
from utils.logging_utils import log_event

DEPARTMENTS = [
    "Digital Banking",
    "Card Operations",
    "Transfers & Payments",
    "Loans & Applications",
    "Customer Service / Branch",
]

INTENT_TO_DEPT = {
    "ACCOUNT_ISSUE": "Digital Banking",
    "CARD_ISSUE": "Card Operations",
    "TRANSFER_ISSUE": "Transfers & Payments",
    "LOAN_ISSUE": "Loans & Applications",
    "COMPLAINT": "Customer Service / Branch",
}

KEYWORD_ROUTING = [
    (
        "Digital Banking",
        [
            "mobil", "mobile app", "internet bank", "login", "otp",
            "şifrə", "parol", "giriş", "приложение",
        ],
    ),
    (
        "Card Operations",
        [
            "kart", "card", "blok", "block", "itmiş", "lost",
            "ödəniş", "payment declined",
        ],
    ),
    (
        "Transfers & Payments",
        [
            "köçürm", "transfer", "uğursuz", "failed", "pul",
            "deducted", "çıxıldı",
        ],
    ),
    (
        "Loans & Applications",
        [
            "kredit", "loan", "borc", "ödəniş plan", "sənəd",
        ],
    ),
    (
        "Customer Service / Branch",
        [
            "filial", "branch", "şikayət", "complaint", "xidmət",
        ],
    ),
]


@dataclass
class RoutingResult:
    department: str
    reason: str


def route_department(
    text: str,
    intent: IntentResult,
    sentiment: Optional[SentimentResult] = None,
) -> RoutingResult:
    lower = text.lower()

    # Intent-based primary routing
    if intent.intent in INTENT_TO_DEPT:
        dept = INTENT_TO_DEPT[intent.intent]
        reason = (
            f"Intent '{intent.intent}' mapped to {dept} "
            f"(confidence {intent.confidence:.0%})"
        )
        log_event("department_routing", department=dept, reason=reason[:120])
        return RoutingResult(dept, reason)

    # Keyword scoring for unclear/general escalation paths
    scores = {d: 0 for d in DEPARTMENTS}
    for dept, keywords in KEYWORD_ROUTING:
        for kw in keywords:
            if kw in lower:
                scores[dept] += 1

    best_dept = max(scores, key=scores.get)
    if scores[best_dept] == 0:
        best_dept = "Customer Service / Branch"
        reason = "No strong keyword match; defaulting to Customer Service / Branch"
    else:
        matched = [kw for kw, _ in [(k, d) for d, kws in KEYWORD_ROUTING for k in kws if k in lower][:3]]
        reason = (
            f"Keyword analysis routed to {best_dept} "
            f"(score {scores[best_dept]}, intent={intent.intent})"
        )

    if sentiment and sentiment.is_critical:
        reason += "; CRITICAL priority due to urgency/emotion"

    log_event("department_routing", department=best_dept, reason=reason[:120])
    return RoutingResult(best_dept, reason)
