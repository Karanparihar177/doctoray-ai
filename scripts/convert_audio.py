
import argparse
from pathlib import Path

from app.services.audio.extractor import extract_audio


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio from a video using FFmpeg"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input video file",
    )

    parser.add_argument(
        "--output",
        default="data/audio/appointment.wav",
        help="Output WAV file",
    )

    args = parser.parse_args()

    output = extract_audio(
        input_path=Path(args.input),
        output_path=Path(args.output),
    )

    print("\nAudio extraction completed!")
    print(f"Output: {output}")
    print(f"Size: {output.stat().st_size / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
