"""Incremental POC workflow: download a recording, convert it to audio,
transcribe it.

Run from the repository root with the virtual environment active:

    python -m scripts.all_scripts download   --url <HTTPS_URL>
    python -m scripts.all_scripts to-opus    --input data/recordings/appointment.mp4
    python -m scripts.all_scripts to-flac    --input data/recordings/appointment.mp4
    python -m scripts.all_scripts transcribe --input data/audio/appointment.opus --language ar-EG
    python -m scripts.all_scripts pipeline   --url <HTTPS_URL>

# download:   streams the video to data/recordings/appointment.mp4. It reuses
#             download_video. Use --output to choose a different path.
# to-opus:    writes mono Opus at 64 kbps (VBR, voip mode) to data/audio/<name>.opus.
# to-flac:    writes FLAC to data/audio/<name>.flac. Compression level 5 by
#             default, --level sets it.
# transcribe: sends an Opus, FLAC or WAV file to Deepgram (Nova-3) and saves
#             data/transcripts/<name>.<language>.json (untouched API response)
#             and .txt (one line per speaker turn). --language is a Deepgram code
#             such as en or ar-EG; --no-diarize skips speaker labels. Speakers are
#             numbers only; doctor/patient roles are assigned in a later step.
#             Needs DEEPGRAM_AI_KEY in .env.
# pipeline:   downloads the video, then converts it to Opus at 64 kbps.
#             --name sets the base file name.
# Safety:     conversions refuse to overwrite existing output unless you pass
#             --force. Only a verified output file is kept.
# Privacy:    the download URL is never printed, since it may be presigned.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from app.services.audio.metadata import inspect_media
from app.services.storage.http_downloader import download_video
from app.services.transcription.deepgram_client import (
    TranscriptionError,
    to_turns,
    transcribe_file,
)

RECORDINGS_DIR = Path("data/recordings")
AUDIO_DIR = Path("data/audio")
TRANSCRIPTS_DIR = Path("data/transcripts")
DEFAULT_NAME = "appointment"
OPUS_BITRATE_KBPS = 64


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    clock = f"{hours}h {minutes:02d}m {secs:02d}s" if hours else f"{minutes}m {secs:02d}s"
    return f"{clock} ({seconds:.2f} s)"


def _report(label: str, path: Path) -> None:
    """Print extension, duration and size plus the stream details."""
    info = inspect_media(path)
    size = info["size_bytes"] or path.stat().st_size

    print(f"\n{label}")
    print(f"  File:      {path}")
    print(f"  Extension: {path.suffix}")
    print(f"  Duration:  {_format_duration(info['duration_seconds'])}")
    print(f"  Size:      {size / (1024 * 1024):.2f} MB ({size} bytes)")

    for stream in info["video_streams"]:
        print(
            f"  Video:     {stream['codec']}, "
            f"{stream['width']}x{stream['height']}"
        )
    for stream in info["audio_streams"]:
        print(
            f"  Audio:     {stream['codec']}, {stream['sample_rate']} Hz, "
            f"{stream['channels']} ch ({stream['channel_layout']})"
        )
    if not info["audio_streams"]:
        print("  Audio:     none (no audio stream found)")


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} was not found on PATH. Install FFmpeg first.")


def _audio_codec(path: Path) -> str | None:
    """Return the codec of the first audio stream, or None if there is none."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe could not read {path.name}")
    streams = json.loads(result.stdout or "{}").get("streams", [])
    return streams[0]["codec_name"] if streams else None


def _encode(
    input_path: Path,
    output_path: Path,
    codec_args: list[str],
    container: str,
    expected_codec: str,
    force: bool,
) -> Path:
    """Run FFmpeg into a temporary file, verify it, then publish it."""
    _require_tool("ffmpeg")
    _require_tool("ffprobe")

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if _audio_codec(input_path) is None:
        raise ValueError(f"{input_path.name} has no audio stream")
    if output_path.exists() and not force:
        raise FileExistsError(
            f"{output_path} already exists (use --force to overwrite)"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".part")

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(input_path),
        "-vn",
        "-map", "0:a:0",
        "-map_metadata", "0",  # keep the source file's tags
        *codec_args,
        "-f", container,
        str(temporary),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr.strip()}")
        if _audio_codec(temporary) != expected_codec:
            raise RuntimeError(f"Output is not a valid {expected_codec} stream")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)

    return output_path


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------

def download(url: str, output: Path) -> Path:
    """Step 1: stream the video from a public HTTPS URL into data/recordings."""
    try:
        return download_video(url=url, destination=output)
    except httpx.HTTPStatusError as exc:
        # Do not surface exc itself: its message contains the URL.
        raise RuntimeError(
            f"Download failed with HTTP {exc.response.status_code}"
        ) from None
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Download failed: {type(exc).__name__}") from None


def to_opus(
    input_path: Path,
    output_path: Path | None = None,
    bitrate_kbps: int = OPUS_BITRATE_KBPS,
    force: bool = False,
) -> Path:
    """Step 2a: extract mono Opus (VBR, voip mode) from a stored video."""
    output_path = output_path or AUDIO_DIR / f"{input_path.stem}.opus"
    return _encode(
        input_path,
        output_path,
        [
            "-ac", "1",
            "-c:a", "libopus",
            "-b:a", f"{bitrate_kbps}k",
            "-vbr", "on",
            "-application", "voip",
        ],
        container="opus",
        expected_codec="opus",
        force=force,
    )


def to_flac(
    input_path: Path,
    output_path: Path | None = None,
    level: int = 5,
    force: bool = False,
) -> Path:
    """Step 2b: extract lossless FLAC from a stored video."""
    output_path = output_path or AUDIO_DIR / f"{input_path.stem}.flac"
    return _encode(
        input_path,
        output_path,
        ["-c:a", "flac", "-compression_level", str(level)],
        container="flac",
        expected_codec="flac",
        force=force,
    )


def _clock(seconds: float | None) -> str:
    minutes, secs = divmod(int(seconds or 0), 60)
    return f"{minutes:02d}:{secs:02d}"


def transcribe(
    input_path: Path,
    language: str,
    output_dir: Path = TRANSCRIPTS_DIR,
    diarize: bool = True,
) -> Path:
    """Step 4: send stored audio to Deepgram and save the transcript.

    Writes the untouched API response (.json) plus a readable speaker-turn
    file (.txt). Speakers are numbers only; roles are assigned later.
    """
    response = transcribe_file(input_path, language=language, diarize=diarize)
    turns = to_turns(response)

    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / f"{input_path.stem}.{language}"
    json_path = Path(f"{base}.json")
    text_path = Path(f"{base}.txt")
    json_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"[{t.index}] [{_clock(t.start)}-{_clock(t.end)}] Speaker {t.speaker}: {t.text}"
        for t in turns
    ]
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    metadata = response.get("metadata", {})
    speakers = sorted({t.speaker for t in turns})
    print("\nTranscription")
    print(f"  Language:  {language}")
    print(f"  Duration:  {_format_duration(metadata.get('duration'))}")
    print(f"  Turns:     {len(turns)}")
    print(f"  Speakers:  {speakers}")
    print(f"  Saved:     {json_path} and {text_path}")
    print("  Preview:")
    for line in lines[:8]:
        print(f"    {line}")

    return json_path


def pipeline(url: str, name: str, force: bool = False) -> Path:
    """Step 3: download the video, then convert it to Opus at 64 kbps."""
    video = download(url, RECORDINGS_DIR / f"{name}.mp4")
    _report("Downloaded video", video)
    return to_opus(video, AUDIO_DIR / f"{name}.opus", force=force)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Doctoray AI POC: download a recording, convert it to audio and transcribe it."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("download", help="Download a video into data/recordings")
    p.add_argument("--url", required=True, help="Public HTTPS video URL")
    p.add_argument(
        "--output",
        type=Path,
        default=RECORDINGS_DIR / f"{DEFAULT_NAME}.mp4",
        help="Local video path",
    )

    p = commands.add_parser("to-opus", help="Convert a stored video to Opus")
    p.add_argument("--input", type=Path, required=True, help="Stored video file")
    p.add_argument("--output", type=Path, help="Default: data/audio/<name>.opus")
    p.add_argument("--bitrate", type=int, default=OPUS_BITRATE_KBPS, help="kbps")
    p.add_argument("--force", action="store_true", help="Overwrite existing output")

    p = commands.add_parser("to-flac", help="Convert a stored video to FLAC")
    p.add_argument("--input", type=Path, required=True, help="Stored video file")
    p.add_argument("--output", type=Path, help="Default: data/audio/<name>.flac")
    p.add_argument("--level", type=int, choices=range(13), default=5)
    p.add_argument("--force", action="store_true", help="Overwrite existing output")

    p = commands.add_parser("transcribe", help="Transcribe stored audio with Deepgram")
    p.add_argument("--input", type=Path, required=True, help="Opus, FLAC or WAV file")
    p.add_argument(
        "--language",
        default="en",
        help="Deepgram language code, for example en or ar-EG",
    )
    p.add_argument("--no-diarize", action="store_true", help="Skip speaker labels")

    p = commands.add_parser(
        "pipeline", help="Download a video, then convert it to Opus at 64 kbps"
    )
    p.add_argument("--url", required=True, help="Public HTTPS video URL")
    p.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help="Base file name for data/recordings/<name>.mp4 and data/audio/<name>.opus",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing audio")

    return parser


def main() -> int:
    args = _build_parser().parse_args()

    try:
        if args.command == "download":
            result = download(args.url, args.output)
        elif args.command == "to-opus":
            result = to_opus(args.input, args.output, args.bitrate, args.force)
        elif args.command == "to-flac":
            result = to_flac(args.input, args.output, args.level, args.force)
        elif args.command == "transcribe":
            transcribe(args.input, args.language, diarize=not args.no_diarize)
            return 0
        else:
            result = pipeline(args.url, args.name, args.force)

        labels = {
            "download": "Downloaded video",
            "to-opus": "Opus audio",
            "to-flac": "FLAC audio",
            "pipeline": "Opus audio",
        }
        _report(labels[args.command], result)
    except (RuntimeError, ValueError, FileNotFoundError, FileExistsError, TranscriptionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
