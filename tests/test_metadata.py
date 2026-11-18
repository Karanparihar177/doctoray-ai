import shutil
import subprocess

import pytest

from app.services.audio.metadata import _to_float, _to_int, inspect_media

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg and FFprobe are required",
)


@pytest.fixture
def video_with_audio(tmp_path):
    path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=d=2:s=160x120",
            "-f", "lavfi", "-i", "sine=d=2",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
    )
    return path


def test_inspect_media_reports_video_and_audio(video_with_audio):
    metadata = inspect_media(video_with_audio)

    assert metadata["has_audio"] is True
    assert metadata["has_video"] is True
    assert isinstance(metadata["duration_seconds"], float)
    assert isinstance(metadata["size_bytes"], int)
    assert metadata["audio_streams"][0]["codec"] == "aac"
    assert isinstance(metadata["audio_streams"][0]["sample_rate"], int)
    assert metadata["video_streams"][0]["width"] == 160
    assert metadata["video_streams"][0]["height"] == 120


def test_inspect_media_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_media(tmp_path / "missing.mp4")


def test_numeric_helpers():
    assert _to_int("48000") == 48000
    assert _to_int(None) is None
    assert _to_int("invalid") is None
    assert _to_float("1089.2") == 1089.2
    assert _to_float(None) is None
    assert _to_float("invalid") is None
