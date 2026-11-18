import pytest
from fastapi.testclient import TestClient

from app.api.v1 import transcriptions
from app.main import app
from app.services.transcription.deepgram_client import TranscriptionError

client = TestClient(app)
URL = "/api/v1/transcriptions"

FAKE_RESPONSE = {
    "metadata": {"request_id": "req-1", "duration": 5.0},
    "results": {
        "utterances": [
            {"speaker": 0, "start": 0.1, "end": 1.0, "transcript": "Hello", "confidence": 0.9},
            {"speaker": 1, "start": 1.2, "end": 2.0, "transcript": "Hi", "confidence": 0.8},
        ]
    },
}


@pytest.fixture
def fake_deepgram(monkeypatch):
    calls = {}

    def fake(path, *, language, diarize=True, **_):
        calls["language"] = language
        calls["diarize"] = diarize
        calls["existed"] = path.is_file()
        calls["path"] = path
        return FAKE_RESPONSE

    monkeypatch.setattr(transcriptions, "transcribe_file", fake)
    return calls


def test_transcription_returns_speaker_turns(fake_deepgram):
    response = client.post(
        URL,
        files={"file": ("a.opus", b"audio-bytes", "audio/ogg")},
        data={"language": "ar-EG"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    assert body["speakers"] == [0, 1]
    assert body["utterances"][0]["text"] == "Hello"
    assert fake_deepgram["language"] == "ar-EG"
    assert fake_deepgram["existed"] is True
    assert not fake_deepgram["path"].exists()  # temp upload is removed


def test_rejects_unsupported_extension(fake_deepgram):
    response = client.post(URL, files={"file": ("a.txt", b"x", "text/plain")})

    assert response.status_code == 415


def test_rejects_invalid_language(fake_deepgram):
    response = client.post(
        URL,
        files={"file": ("a.opus", b"x", "audio/ogg")},
        data={"language": "../etc"},
    )

    assert response.status_code == 422


def test_rejects_empty_file(fake_deepgram):
    response = client.post(URL, files={"file": ("a.opus", b"", "audio/ogg")})

    assert response.status_code == 400


def test_rejects_oversized_file(fake_deepgram, monkeypatch):
    monkeypatch.setattr(transcriptions.settings, "max_upload_mb", 0)

    response = client.post(URL, files={"file": ("a.opus", b"x", "audio/ogg")})

    assert response.status_code == 413


def test_provider_error_becomes_502(monkeypatch):
    def failing(*_, **__):
        raise TranscriptionError("Deepgram returned HTTP 401")

    monkeypatch.setattr(transcriptions, "transcribe_file", failing)

    response = client.post(URL, files={"file": ("a.opus", b"x", "audio/ogg")})

    assert response.status_code == 502
