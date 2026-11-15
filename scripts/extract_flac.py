
import argparse
from pathlib import Path

from app.services.audio.flac_extractor import extract_audio_to_flac


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio directly from video into FLAC."
    )

    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument(
        "--output",
        default="data/audio/appointment.flac",
        help="Output FLAC path",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=range(13),
        default=5,
        help="FLAC compression level (0-12)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    result = extract_audio_to_flac(
        input_path,
        output_path,
        args.level,
    )

    input_size = input_path.stat().st_size
    output_size = result.stat().st_size
    reduction = (1 - output_size / input_size) * 100

    print("\nFLAC extraction completed successfully!")
    print(f"Output: {result}")
    print(f"Video size: {input_size / (1024 * 1024):.2f} MB")
    print(f"FLAC size: {output_size / (1024 * 1024):.2f} MB")
    print(f"Size reduction: {reduction:.2f}%")


if __name__ == "__main__":
    main()
