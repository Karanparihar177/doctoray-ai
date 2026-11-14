
import shutil
import subprocess

import pytest

from app.services.audio.extractor import extract_audio
from app.services.audio.metadata import inspect_media


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required",
)


@pytest.fixture
def video_with_audio(tmp_path):
    """Generate a 1-second synthetic video with a sine-wave audio track."""

    output = tmp_path / "test_with_audio.mp4"

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "lavfi",
        "-i", "color=c=black:s=160x120:d=1",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:sample_rate=48000:duration=1",
        "-shortest",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output),
    ]

    subprocess.run(command, check=True, capture_output=True)
    return output


@pytest.fixture
def video_without_audio(tmp_path):
    """Generate a 1-second video without an audio track."""

    output = tmp_path / "test_without_audio.mp4"

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "lavfi",
        "-i", "color=c=black:s=160x120:d=1",
        "-t", "1",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output),
    ]

    subprocess.run(command, check=True, capture_output=True)
    return output


def test_extract_audio_success(video_with_audio, tmp_path):
    output = tmp_path / "output.wav"

    result = extract_audio(video_with_audio, output)

    assert result.exists()
    assert result.stat().st_size > 44

    metadata = inspect_media(result)

    assert metadata["has_audio"] is True
    assert metadata["audio_streams"][0]["codec"] == "pcm_s16le"
    assert metadata["audio_streams"][0]["sample_rate"] == "48000"
    assert metadata["audio_streams"][0]["channels"] == 1


def test_missing_input_file(tmp_path):
    missing_file = tmp_path / "missing.mp4"
    output = tmp_path / "output.wav"

    with pytest.raises(FileNotFoundError):
        extract_audio(missing_file, output)


def test_video_without_audio(video_without_audio, tmp_path):
    output = tmp_path / "output.wav"

    with pytest.raises(ValueError, match="does not contain an audio stream"):
        extract_audio(video_without_audio, output)


def test_existing_output_file(video_with_audio, tmp_path):
    output = tmp_path / "output.wav"
    output.write_bytes(b"existing file")

    with pytest.raises(FileExistsError):
        extract_audio(video_with_audio, output)

    assert output.read_bytes() == b"existing file"


def test_invalid_media_file(tmp_path):
    invalid_file = tmp_path / "invalid.mp4"
    output = tmp_path / "output.wav"

    invalid_file.write_text("This is not a valid video")

    with pytest.raises(RuntimeError, match="FFprobe failed"):
        extract_audio(invalid_file, output)
