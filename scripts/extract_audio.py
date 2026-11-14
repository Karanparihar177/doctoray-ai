import argparse
from pathlib import Path

from app.services.storage.http_downloader import download_video


def main():
    parser = argparse.ArgumentParser(
        description="Download a Doctoray video recording"
    )

    parser.add_argument(
        "--url",
        required=True,
        help="Public HTTPS video URL",
    )

    parser.add_argument(
        "--output",
        default="data/recordings/appointment.mp4",
        help="Local output path",
    )

    args = parser.parse_args()

    output_path = download_video(
        url=args.url,
        destination=Path(args.output),
    )

    print(f"Download completed: {output_path}")
    print(f"File size: {output_path.stat().st_size / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
