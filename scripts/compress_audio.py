
import argparse
from pathlib import Path

from app.services.audio.compressor import compress_audio_to_flac


def main():
    parser = argparse.ArgumentParser(
        description="Convert audio to lossless FLAC"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input audio file",
    )

    parser.add_argument(
        "--output",
        default="data/audio/appointment.flac",
        help="Output FLAC file",
    )

    parser.add_argument(
        "--level",
        type=int,
        default=5,
        choices=range(13),
        help="FLAC compression level (0-12, default 5)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    flac_path = compress_audio_to_flac(
        input_path=input_path,
        output_path=output_path,
        compression_level=args.level,
    )

    original_size = input_path.stat().st_size
    compressed_size = flac_path.stat().st_size

    reduction = (1 - compressed_size / original_size) * 100

    print("\nFLAC conversion completed!")
    print(f"Output: {flac_path}")
    print(f"Original size: {original_size / (1024 * 1024):.2f} MB")
    print(f"FLAC size: {compressed_size / (1024 * 1024):.2f} MB")
    print(f"Size reduction: {reduction:.2f}%")


if __name__ == "__main__":
    main()
