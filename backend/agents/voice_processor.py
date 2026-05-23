"""Voice transcription via OpenAI Whisper."""

import io
import tempfile
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from config import get_settings
from utils.logging_utils import log_event
from utils.token_tracker import token_tracker

settings = get_settings()


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration_estimate: float = 0.0


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language_hint: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe voice using whisper-1.
    Supports Azerbaijani (az) and Russian (ru).
    """
    if not settings.openai_api_key:
        log_event("transcription_skipped", reason="no_api_key")
        return TranscriptionResult(
            text="[Voice transcription requires OPENAI_API_KEY]",
            language="az",
        )

    client = OpenAI(api_key=settings.openai_api_key)
    suffix = ".webm"
    if "." in filename:
        suffix = "." + filename.rsplit(".", 1)[-1]

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            with open(tmp.name, "rb") as audio_file:
                kwargs = {
                    "model": "whisper-1",
                    "file": audio_file,
                    "response_format": "verbose_json",
                }
                if language_hint in ("az", "ru", "en"):
                    kwargs["language"] = language_hint

                result = client.audio.transcriptions.create(**kwargs)

        text = result.text if hasattr(result, "text") else str(result)
        lang = getattr(result, "language", None) or language_hint or "az"

        # Whisper billed per minute — approximate 1 min = 1 unit
        token_tracker.record("whisper-1", 1000, 0)

        log_event(
            "transcription_done",
            language=lang,
            text_length=len(text),
        )
        return TranscriptionResult(text=text.strip(), language=lang)
    except Exception as e:
        log_event("transcription_error", error=str(e)[:100])
        raise
