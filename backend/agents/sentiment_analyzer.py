"""Sentiment and emotion analysis using gpt-4o-mini."""

import json
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from config import get_settings
from utils.emoji_analyzer import EmojiAnalysis, analyze_emojis, apply_emoji_to_scores
from utils.logging_utils import log_event
from utils.token_tracker import token_tracker

settings = get_settings()
MAX_TOKENS = 500

SYSTEM_PROMPT = """You analyze customer support messages for AccessBank Azerbaijan.
Return ONLY valid JSON with keys:
- sentiment: POSITIVE | NEUTRAL | NEGATIVE
- emotion: ANGRY | FRUSTRATED | SAD | NEUTRAL | HAPPY | URGENT
- urgency_score: integer 1-5 (1=low, 5=critical)
Consider: complaints about lost money, no response, blocked cards = higher urgency.
Respond in the same language context as the message."""


@dataclass
class SentimentResult:
    sentiment: str
    emotion: str
    urgency_score: int
    is_critical: bool
    emojis_found: list
    raw: Optional[dict] = None


def _fallback_analysis(text: str, emoji: EmojiAnalysis) -> SentimentResult:
    negative_words = [
        "uğursuz", "problem", "şikayət", "narazı", "blok", "itdi",
        "failed", "angry", "плохо", "ужас",
    ]
    urgent_words = ["təcili", "dərhal", "urgent", "срочно", "cavab yoxdu"]
    sentiment = "NEUTRAL"
    emotion = "NEUTRAL"
    urgency = 2

    lower = text.lower()
    if any(w in lower for w in negative_words):
        sentiment = "NEGATIVE"
        emotion = "FRUSTRATED"
        urgency = 3
    if any(w in lower for w in urgent_words):
        emotion = "URGENT"
        urgency = 4
    if "😡" in text or emoji.angry_boost >= 2:
        emotion = "ANGRY"
        sentiment = "NEGATIVE"
        urgency = max(urgency, 4)

    sentiment, emotion, urgency = apply_emoji_to_scores(
        sentiment, emotion, urgency, emoji
    )
    is_critical = urgency >= 4 or emotion in ("ANGRY", "URGENT")
    return SentimentResult(
        sentiment=sentiment,
        emotion=emotion,
        urgency_score=urgency,
        is_critical=is_critical,
        emojis_found=emoji.emojis_found,
    )


def analyze_sentiment(text: str) -> SentimentResult:
    emoji = analyze_emojis(text)

    if not settings.openai_api_key:
        result = _fallback_analysis(text, emoji)
        log_event(
            "sentiment_result",
            emotion=result.emotion,
            score=result.urgency_score,
            emojis=len(emoji.emojis_found),
            mode="fallback",
        )
        return result

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=150,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Message:\n{text[:1500]}\n\nEmoji hints: angry={emoji.angry_boost}, urgency={emoji.urgency_boost}",
                },
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
        sentiment = str(data.get("sentiment", "NEUTRAL")).upper()
        emotion = str(data.get("emotion", "NEUTRAL")).upper()
        urgency = int(data.get("urgency_score", 2))
        urgency = max(1, min(5, urgency))

        sentiment, emotion, urgency = apply_emoji_to_scores(
            sentiment, emotion, urgency, emoji
        )
        is_critical = urgency >= 4 or emotion in ("ANGRY", "URGENT")

        log_event(
            "sentiment_result",
            emotion=emotion,
            score=urgency,
            emojis=len(emoji.emojis_found),
        )
        return SentimentResult(
            sentiment=sentiment,
            emotion=emotion,
            urgency_score=urgency,
            is_critical=is_critical,
            emojis_found=emoji.emojis_found,
            raw=data,
        )
    except Exception as e:
        log_event("sentiment_error", error=str(e)[:100])
        return _fallback_analysis(text, emoji)
