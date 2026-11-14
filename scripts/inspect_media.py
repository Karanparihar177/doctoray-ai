
import argparse
import json
from pathlib import Path

from app.services.audio.metadata import inspect_media


def main():
    parser = argparse.ArgumentParser(
        description="Inspect video and audio metadata"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the video file",
    )

    args = parser.parse_args()

    metadata = inspect_media(Path(args.input))

    print(json.dumps(metadata, indent=4))

    if not metadata["has_audio"]:
        print("\nWARNING: No audio stream found!")

    else:
        print("\nAudio stream detected successfully.")


if __name__ == "__main__":
    main()
