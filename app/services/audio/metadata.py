import json
import subprocess
from pathlib import Path


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def inspect_media(path: Path) -> dict:
    """Return format, video-stream and audio-stream metadata using FFprobe."""
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: {path}")

    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_format", "-show_streams",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ValueError(f"FFprobe could not read {path.name}")

    data = json.loads(result.stdout or "{}")
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_streams = [
        {
            "codec": s.get("codec_name"),
            "width": _to_int(s.get("width")),
            "height": _to_int(s.get("height")),
        }
        for s in streams
        if s.get("codec_type") == "video"
    ]

    audio_streams = [
        {
            "codec": s.get("codec_name"),
            "sample_rate": _to_int(s.get("sample_rate")),
            "channels": _to_int(s.get("channels")),
            "channel_layout": s.get("channel_layout"),
        }
        for s in streams
        if s.get("codec_type") == "audio"
    ]

    return {
        "file_name": path.name,
        "format": fmt.get("format_name"),
        "duration_seconds": _to_float(fmt.get("duration")),
        "size_bytes": _to_int(fmt.get("size")),
        "has_video": bool(video_streams),
        "has_audio": bool(audio_streams),
        "video_streams": video_streams,
        "audio_streams": audio_streams,
    }
