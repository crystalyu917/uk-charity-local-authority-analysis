"""Cached, atomic file downloads."""

from logging import getLogger
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

import requests

from uk_charity_local_authority_analysis.core.datasets.constants import (
    DEFAULT_STAGING_DIR,
)

logger = getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 300


def download_file(
    url: str,
    dest_dir: Path | None = None,
    *,
    filename: str | None = None,
) -> Path:
    """Download a file unless it is already cached.

    Parameters
    ----------
    url : str
        URL of the file to download.
    dest_dir : Path, optional
        Destination directory. Defaults to the shared staging directory.
    filename : str, optional
        Local filename. Defaults to the decoded filename in the URL path.

    Returns
    -------
    Path
        Path to the downloaded or cached file.

    """
    destination_dir = dest_dir if dest_dir is not None else DEFAULT_STAGING_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = PurePosixPath(unquote(urlsplit(url).path)).name
        if not filename:
            raise ValueError("url must contain a filename")

    if (
        not filename
        or filename in {".", ".."}
        or "\x00" in filename
        or PurePosixPath(filename).name != filename
        or PureWindowsPath(filename).name != filename
    ):
        raise ValueError("filename must be a safe basename")

    destination_path = destination_dir / filename
    if destination_path.is_file() and not destination_path.is_symlink():
        logger.info("Using cached data at %s", destination_path)
        return destination_path

    with TemporaryDirectory(
        dir=destination_dir,
        prefix=f".{filename}.",
    ) as temporary_dir:
        temporary_path = Path(temporary_dir) / f"{filename}.part"
        with (
            requests.get(
                url,
                stream=True,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            ) as response,
            temporary_path.open("wb") as temporary_file,
        ):
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                if chunk:
                    _ = temporary_file.write(chunk)

        _ = temporary_path.replace(destination_path)

    logger.info("Downloaded data to %s", destination_path)
    return destination_path
