
import argparse
from pathlib import Path

from app.services.audio.metadata import inspect_media


def format_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"


def benchmark_audio(file_path: Path) -> dict:
    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    metadata = inspect_media(file_path)

    if not metadata["audio_streams"]:
        raise ValueError(f"No audio stream found: {file_path}")

    audio = metadata["audio_streams"][0]

    duration = metadata["duration_seconds"]
    size_bytes = metadata["size_bytes"]

    if not duration or not size_bytes:
        raise ValueError(f"Missing duration or size metadata: {file_path}")

    # Calculate average bitrate from the complete file size.
    bitrate_kbps = (size_bytes * 8) / duration / 1000

    return {
        "name": file_path.name,
        "codec": audio["codec"],
        "size_bytes": size_bytes,
        "size_mb": size_bytes / (1024 * 1024),
        "duration": duration,
        "sample_rate": audio["sample_rate"],
        "channels": audio["channels"],
        "bitrate_kbps": bitrate_kbps,
    }


def print_report(results: list[dict]) -> None:
    wav_size = next(
        item["size_bytes"]
        for item in results
        if item["codec"] == "pcm_s16le"
    )

    print("\n" + "=" * 100)
    print("DOCTORAY AUDIO BENCHMARK")
    print("=" * 100)

    print(
        f"{'FORMAT':<10}"
        f"{'SIZE (MB)':>12}"
        f"{'DURATION':>12}"
        f"{'BITRATE':>14}"
        f"{'SAMPLE RATE':>15}"
        f"{'CHANNELS':>12}"
        f"{'REDUCTION':>14}"
    )

    print("-" * 100)

    for item in results:
        reduction = (1 - item["size_bytes"] / wav_size) * 100

        print(
            f"{item['codec']:<10}"
            f"{item['size_mb']:>12.2f}"
            f"{format_duration(item['duration']):>12}"
            f"{item['bitrate_kbps']:>11.2f} kbps"
            f"{item['sample_rate']:>15}"
            f"{item['channels']:>12}"
            f"{reduction:>13.2f}%"
        )

    print("=" * 100)

    print("\nDetailed file information:")

    for item in results:
        print(f"\nFile: {item['name']}")
        print(f"Codec: {item['codec']}")
        print(f"Size: {item['size_mb']:.2f} MB")
        print(f"Duration: {item['duration']:.2f} seconds")


def validate_duration_consistency(
    results: list[dict],
    tolerance_seconds: float = 1.0,
) -> None:
    reference_duration = results[0]["duration"]
    for item in results[1:]:
        difference = abs(item["duration"] - reference_duration)
        if difference > tolerance_seconds:
            raise ValueError(
                f"Duration mismatch: {item['name']} differs from "
                f"the reference by {difference:.2f} seconds."
            )
    print("\nDuration validation: PASSED")


def main():
    parser = argparse.ArgumentParser(
        description="Compare WAV, FLAC and Opus audio files."
    )

    parser.add_argument("--wav", required=True)
    parser.add_argument("--flac", required=True)
    parser.add_argument("--opus", required=True)

    args = parser.parse_args()

    files = [
        Path(args.wav),
        Path(args.flac),
        Path(args.opus),
    ]

    results = [benchmark_audio(path) for path in files]

    validate_duration_consistency(results)
    
    print_report(results)


if __name__ == "__main__":
    main()
