
from pathlib import Path
import tempfile

import httpx


DEFAULT_MAX_SIZE = 600 * 1024 * 1024  # 600 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB


def download_video(
    url: str,
    destination: Path,
    max_bytes: int = DEFAULT_MAX_SIZE,
) -> Path:
    """
    Stream a video from a trusted public HTTPS URL to local disk.

    Downloads to a temporary file first and only publishes the
    destination after the complete download succeeds.
    """

    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs are supported")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None
    downloaded_bytes = 0

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f"{destination.name}.",
            suffix=".part",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            timeout = httpx.Timeout(60.0, connect=15.0)

            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
            ) as client:

                with client.stream("GET", url) as response:
                    response.raise_for_status()

                    content_length = response.headers.get(
                        "content-length"
                    )

                    if content_length:
                        if int(content_length) > max_bytes:
                            raise ValueError(
                                "Video exceeds the maximum allowed size"
                            )

                    for chunk in response.iter_bytes(
                        chunk_size=CHUNK_SIZE
                    ):
                        if not chunk:
                            continue

                        downloaded_bytes += len(chunk)

                        if downloaded_bytes > max_bytes:
                            raise ValueError(
                                "Video exceeds the maximum allowed size"
                            )

                        temporary_file.write(chunk)

        if downloaded_bytes == 0:
            raise ValueError("Downloaded video is empty")

        # Atomic rename: incomplete files never appear at destination.
        temporary_path.replace(destination)

        return destination

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
