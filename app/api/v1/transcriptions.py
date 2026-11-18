import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.services.transcription.deepgram_client import (
    TranscriptionError,
    to_utterances,
    transcribe_file,
)

router = APIRouter(prefix="/transcriptions", tags=["Transcriptions"])

ALLOWED_EXTENSIONS = {".opus", ".ogg", ".flac", ".wav", ".mp3"}
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
CHUNK_SIZE = 1024 * 1024


@router.post("")
def create_transcription(
    file: UploadFile = File(..., description="Opus, FLAC, WAV, OGG or MP3 audio"),
    language: str = Form("en", description="Deepgram language code, e.g. en or ar-EG"),
    diarize: bool = Form(True, description="Label speakers as numbers"),
):
    """Transcribe one uploaded audio file with Deepgram and return speaker turns.

    The upload is kept only in a temporary file that is deleted afterwards.
    Speakers are numbers; deciding which one is the doctor happens later.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Use one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if not LANGUAGE_PATTERN.match(language):
        raise HTTPException(status_code=422, detail="Invalid language code")

    max_bytes = settings.max_upload_mb * 1024 * 1024

    with tempfile.TemporaryDirectory(prefix="doctoray-") as tmp_dir:
        audio_path = Path(tmp_dir) / f"upload{suffix}"

        received = 0
        with audio_path.open("wb") as out:
            while chunk := file.file.read(CHUNK_SIZE):
                received += len(chunk)
                if received > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.max_upload_mb} MB",
                    )
                out.write(chunk)

        if received == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        try:
            response = transcribe_file(audio_path, language=language, diarize=diarize)
        except TranscriptionError as exc:
            status = 503 if "not set" in str(exc) else 502
            raise HTTPException(status_code=status, detail=str(exc)) from None

    turns = to_utterances(response)
    metadata = response.get("metadata", {})

    return {
        "request_id": metadata.get("request_id"),
        "language": language,
        "duration_seconds": metadata.get("duration"),
        "speakers": sorted({t["speaker"] for t in turns if t["speaker"] is not None}),
        "utterances": turns,
    }
