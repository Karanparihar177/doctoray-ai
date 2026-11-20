"""Deepgram pre-recorded speech-to-text over the REST API.

Only the transcription call lives here. Speaker roles (doctor / patient)
are decided later; Deepgram only returns numbered speakers.
"""

import mimetypes
from pathlib import Path

import httpx

from app.core.config import settings
from app.schemas.consultation import TranscriptTurn

CONTENT_TYPES = {
    ".opus": "audio/ogg",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
}

# Deepgram aborts requests that run longer than 10 minutes.
TIMEOUT = httpx.Timeout(600.0, connect=15.0)


class TranscriptionError(RuntimeError):
    """Raised for configuration, HTTP or response problems."""


def transcribe_file(
    path: Path,
    *,
    language: str,
    diarize: bool = True,
    mip_opt_out: bool = True,
) -> dict:
    """Send one local audio file to Deepgram and return the raw JSON."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    if settings.deepgram_ai_key is None:
        raise TranscriptionError("DEEPGRAM_AI_KEY is not set in .env")

    params = {
        "model": settings.deepgram_model,
        "language": language,
        "punctuate": "true",
        "smart_format": "true",
        "utterances": "true",
        "mip_opt_out": str(mip_opt_out).lower(),
    }
    if diarize:
        params["diarize_model"] = "latest"

    content_type = (
        CONTENT_TYPES.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )

    try:
        response = httpx.post(
            f"{settings.deepgram_base_url.rstrip('/')}/v1/listen",
            params=params,
            headers={
                "Authorization": f"Token {settings.deepgram_ai_key.get_secret_value()}",
                "Content-Type": content_type,
            },
            content=path.read_bytes(),
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("err_msg", "")
        except ValueError:
            detail = ""
        raise TranscriptionError(
            f"Deepgram returned HTTP {exc.response.status_code}: {detail}".rstrip(": ")
        ) from None
    except httpx.HTTPError as exc:
        raise TranscriptionError(f"Deepgram request failed: {type(exc).__name__}") from None

    return response.json()


def to_utterances(response: dict) -> list[dict]:
    """Flatten Deepgram's response into speaker turns."""
    utterances = response.get("results", {}).get("utterances") or []
    return [
        {
            "speaker": u.get("speaker"),
            "start": u.get("start"),
            "end": u.get("end"),
            "text": u.get("transcript", ""),
            "confidence": u.get("confidence"),
        }
        for u in utterances
    ]


def to_turns(response: dict) -> list[TranscriptTurn]:
    """Build speaker turns from word-level speaker labels.

    Deepgram's utterances can contain words from both speakers, so the
    LLM input is rebuilt here: a new turn starts whenever the speaker changes.
    """
    channels = response.get("results", {}).get("channels") or [{}]
    alternatives = channels[0].get("alternatives") or [{}]
    words = alternatives[0].get("words") or []

    turns: list[TranscriptTurn] = []
    for word in words:
        speaker = word.get("speaker", 0)
        text = word.get("punctuated_word") or word.get("word", "")
        if turns and turns[-1].speaker == speaker:
            last = turns[-1]
            turns[-1] = last.model_copy(
                update={"text": f"{last.text} {text}", "end": word.get("end")}
            )
        else:
            turns.append(
                TranscriptTurn(
                    index=len(turns),
                    speaker=speaker,
                    start=word.get("start"),
                    end=word.get("end"),
                    text=text,
                )
            )
    return turns
