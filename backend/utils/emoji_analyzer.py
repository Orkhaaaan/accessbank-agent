"""Emoji detection and sentiment/emotion boosts."""

import re
from dataclasses import dataclass
from typing import List, Tuple

ANGRY_EMOJIS = {"😡", "🤬", "💢", "👿", "😠"}
SAD_EMOJIS = {"😢", "😭", "😞", "💔", "🥺"}
POSITIVE_EMOJIS = {"😊", "👍", "🙏", "❤️", "✅", "😄"}
URGENCY_EMOJIS = {"❗", "‼️", "🚨", "⚠️", "🔴"}

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


@dataclass
class EmojiAnalysis:
    emojis_found: List[str]
    angry_boost: int
    sad_boost: int
    positive_boost: int
    urgency_boost: int


def analyze_emojis(text: str) -> EmojiAnalysis:
    emojis = EMOJI_PATTERN.findall(text)
    flat = []
    for e in emojis:
        flat.extend(list(e))

    angry = sum(1 for e in flat if e in ANGRY_EMOJIS)
    sad = sum(1 for e in flat if e in SAD_EMOJIS)
    positive = sum(1 for e in flat if e in POSITIVE_EMOJIS)
    urgency = sum(1 for e in flat if e in URGENCY_EMOJIS)
    # Double exclamation marks in text
    urgency += text.count("!!") + text.count("❗❗")

    return EmojiAnalysis(
        emojis_found=flat,
        angry_boost=min(angry * 2, 4),
        sad_boost=min(sad * 2, 3),
        positive_boost=min(positive * 2, 3),
        urgency_boost=min(urgency * 2, 4),
    )


def apply_emoji_to_scores(
    sentiment: str,
    emotion: str,
    urgency: int,
    emoji: EmojiAnalysis,
) -> Tuple[str, str, int]:
    urgency = min(5, urgency + emoji.urgency_boost)

    if emoji.angry_boost >= 2:
        emotion = "ANGRY"
        sentiment = "NEGATIVE"
        urgency = max(urgency, 4)
    elif emoji.sad_boost >= 2:
        emotion = "SAD"
        sentiment = "NEGATIVE"
    elif emoji.positive_boost >= 2:
        if sentiment == "NEGATIVE":
            sentiment = "NEUTRAL"
        if emotion in ("ANGRY", "FRUSTRATED"):
            emotion = "NEUTRAL"
        if sentiment == "NEUTRAL":
            sentiment = "POSITIVE"
            emotion = "HAPPY"

    if emoji.urgency_boost >= 2:
        emotion = "URGENT"
        urgency = max(urgency, 4)

    return sentiment, emotion, urgency
