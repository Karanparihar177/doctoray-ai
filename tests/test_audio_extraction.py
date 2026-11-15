
import hashlib
import shutil
import subprocess

import pytest

from app.services.audio.compressor import compress_audio_to_flac
from app.services.audio.flac_extractor import extract_audio_to_flac
from app.services.audio.opus_extractor import extract_audio_to_opus
from app.services.audio.extractor import extract_audio
from app.services.audio.metadata import inspect_media, _to_int, _to_float


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
    assert metadata["audio_streams"][0]["sample_rate"] == 48000
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


def decoded_pcm_hash(file_path):
    """Hash decoded 48 kHz mono 16-bit PCM samples."""

    result = subprocess.run(
        [
            "ffmpeg",
            "-v", "error",
            "-i", str(file_path),
            "-map", "0:a:0",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ar", "48000",
            "-ac", "1",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )

    return hashlib.sha256(result.stdout).hexdigest()


def test_compress_audio_to_flac_losslessly(video_with_audio, tmp_path):
    wav_path = tmp_path / "original.wav"
    flac_path = tmp_path / "compressed.flac"

    extract_audio(video_with_audio, wav_path)

    result = compress_audio_to_flac(wav_path, flac_path)

    assert result.exists()

    metadata = inspect_media(result)

    assert metadata["audio_streams"][0]["codec"] == "flac"
    assert metadata["audio_streams"][0]["sample_rate"] == 48000
    assert metadata["audio_streams"][0]["channels"] == 1

    assert decoded_pcm_hash(wav_path) == decoded_pcm_hash(flac_path)


def test_compression_rejects_existing_output(video_with_audio, tmp_path):
    wav_path = tmp_path / "original.wav"
    flac_path = tmp_path / "existing.flac"

    extract_audio(video_with_audio, wav_path)
    flac_path.write_bytes(b"existing content")

    with pytest.raises(FileExistsError):
        compress_audio_to_flac(wav_path, flac_path)

    assert flac_path.read_bytes() == b"existing content"


def test_compression_rejects_invalid_level(video_with_audio, tmp_path):
    wav_path = tmp_path / "original.wav"
    flac_path = tmp_path / "output.flac"

    extract_audio(video_with_audio, wav_path)

    with pytest.raises(ValueError, match="Compression level"):
        compress_audio_to_flac(
            wav_path,
            flac_path,
            compression_level=13,
        )


def test_direct_video_to_flac_is_lossless(
    video_with_audio,
    tmp_path,
):
    wav_path = tmp_path / "reference.wav"
    flac_path = tmp_path / "direct.flac"

    extract_audio(video_with_audio, wav_path)
    extract_audio_to_flac(video_with_audio, flac_path)

    metadata = inspect_media(flac_path)

    assert metadata["audio_streams"][0]["codec"] == "flac"
    assert metadata["audio_streams"][0]["sample_rate"] == 48000
    assert metadata["audio_streams"][0]["channels"] == 1

    assert decoded_pcm_hash(wav_path) == decoded_pcm_hash(flac_path)


def test_extract_audio_to_opus_success(video_with_audio, tmp_path):
    output_path = tmp_path / "output.opus"

    result = extract_audio_to_opus(
        video_with_audio,
        output_path,
        bitrate_kbps=64,
    )

    metadata = inspect_media(result)
    audio = metadata["audio_streams"][0]

    assert result.exists()
    assert audio["codec"] == "opus"
    assert audio["channels"] == 1
    assert audio["sample_rate"] == 48000

    # Audio duration should remain close to the source duration.
    source_metadata = inspect_media(video_with_audio)
    assert abs(
        metadata["duration_seconds"]
        - source_metadata["duration_seconds"]
    ) < 1.0


def test_opus_rejects_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_audio_to_opus(
            tmp_path / "missing.mp4",
            tmp_path / "output.opus",
        )


def test_opus_rejects_video_without_audio(
    video_without_audio,
    tmp_path,
):
    with pytest.raises(ValueError, match="does not contain an audio"):
        extract_audio_to_opus(
            video_without_audio,
            tmp_path / "output.opus",
        )


def test_opus_rejects_existing_output(
    video_with_audio,
    tmp_path,
):
    output_path = tmp_path / "existing.opus"
    output_path.write_bytes(b"existing content")

    with pytest.raises(FileExistsError):
        extract_audio_to_opus(
            video_with_audio,
            output_path,
        )

    assert output_path.read_bytes() == b"existing content"


def test_opus_rejects_invalid_bitrate(
    video_with_audio,
    tmp_path,
):
    with pytest.raises(ValueError, match="Bitrate"):
        extract_audio_to_opus(
            video_with_audio,
            tmp_path / "output.opus",
            bitrate_kbps=300,
        )


def test_metadata_returns_normalized_numeric_types(video_with_audio):
    metadata = inspect_media(video_with_audio)

    audio = metadata["audio_streams"][0]
    video = metadata["video_streams"][0]

    assert isinstance(metadata["duration_seconds"], float)
    assert isinstance(metadata["size_bytes"], int)

    assert isinstance(audio["sample_rate"], int)
    assert isinstance(audio["channels"], int)

    assert isinstance(video["width"], int)
    assert isinstance(video["height"], int)


def test_metadata_numeric_helpers_handle_valid_values():
    assert _to_int("48000") == 48000
    assert _to_int("2") == 2

    assert _to_float("1089.201167") == 1089.201167
    assert _to_float("60") == 60.0


def test_metadata_numeric_helpers_handle_invalid_values():
    assert _to_int(None) is None
    assert _to_int("invalid") is None

    assert _to_float(None) is None
    assert _to_float("invalid") is None
