"""Shared file downloads and ZIP extraction.

scripts/download_and_extract.py selects sources and dated destinations, then calls
download_file and extract_zip with refresh=True on every run. These library
helpers default to cache reuse for callers that do not request a refresh.
Extraction reads local files; only download_file uses the
network. Companies House ZIPs use the same generic extraction as other sources.
"""

from logging import getLogger
from ntpath import isreserved
from pathlib import Path, PurePosixPath, PureWindowsPath
from shutil import copyfileobj
from stat import S_IFMT, S_IFREG
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, ZipInfo

import requests

from uk_charity_local_authority_analysis.charity_commission_register.filepath import (
    DEFAULT_STAGING_DIR,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = getLogger(__name__)

_COPY_BUFFER_SIZE = 1024 * 1024
_UNIX_CREATE_SYSTEM = 3


def extract_single_file_zip(
    zip_path: str | Path,
    dest_dir: Path | None = None,
    *,
    output_filepath: Path | None = None,
) -> Path:
    """Extract the sole file in a ZIP archive using an atomic write.

    A cached file is reused when its size matches the uncompressed size
    recorded in the archive; cached contents are not compared. The member must
    have a plain filename without directories. For a full refresh, use
    extract_zip(..., refresh=True).

    Parameters
    ----------
    zip_path : str or Path
        ZIP archive containing exactly one non-directory member.
    dest_dir : Path, optional
        Parent directory for the archive-named extraction directory.
        Defaults to the shared staging directory.
    output_filepath : Path, optional
        Exact output filename. Overrides the archive-named destination while
        retaining member validation, caching, and atomic publication.

    Returns
    -------
    Path
        Path to the extracted or cached file.

    """
    resolved_zip_path = Path(zip_path)
    destination_dir = dest_dir if dest_dir is not None else DEFAULT_STAGING_DIR
    extract_dir = destination_dir / resolved_zip_path.stem

    with ZipFile(resolved_zip_path, "r") as archive:
        member = _single_file_member(archive)
        member_name = _safe_member_basename(member)
        if output_filepath is not None:
            return _extract_member(
                archive, member, output_filepath.parent, Path(output_filepath.name),
            )
        return _extract_member(
            archive,
            member,
            extract_dir,
            Path(member_name),
        )


def extract_zip_members(
    zip_path: str | Path,
    member_names: Sequence[str],
    dest_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Extract selected ZIP members while preserving safe relative paths.

    Reuse existing files with matching uncompressed sizes and publish each new
    file atomically. Unselected files already in the destination are retained.

    Parameters
    ----------
    zip_path : str or Path
        ZIP archive containing the requested members.
    member_names : sequence of str
        Exact archive member names to extract.
    dest_dir : Path, optional
        Parent directory for the archive-named extraction directory.
        Defaults to the shared staging directory.

    Returns
    -------
    tuple of Path
        Extracted paths in the same order as ``member_names``.

    """
    requested_names = tuple(member_names)
    if not requested_names:
        raise ValueError("member_names must contain at least one member")
    if len(set(requested_names)) != len(requested_names):
        raise ValueError("member_names must not contain duplicates")
    relative_paths = tuple(
        _safe_relative_path(requested_name) for requested_name in requested_names
    )
    windows_paths = tuple(
        str(PureWindowsPath(requested_name)).casefold()
        for requested_name in requested_names
    )
    if len(set(windows_paths)) != len(windows_paths):
        raise ValueError("member_names must not resolve to the same Windows path")

    resolved_zip_path = Path(zip_path)
    destination_dir = dest_dir if dest_dir is not None else DEFAULT_STAGING_DIR
    extract_dir = destination_dir / resolved_zip_path.stem

    with ZipFile(resolved_zip_path, "r") as archive:
        archive_members = _unique_archive_members(archive)
        missing_names = set(requested_names).difference(archive_members)
        if missing_names:
            missing = ", ".join(sorted(missing_names))
            raise ValueError(f"ZIP members were not found: {missing}")

        selected_members = tuple(archive_members[name] for name in requested_names)
        for member in selected_members:
            _validate_regular_file(member)
        return tuple(
            _extract_member(archive, member, extract_dir, relative_path)
            for member, relative_path in zip(
                selected_members, relative_paths, strict=True
            )
        )


def extract_zip(zip_path: str | Path, *, refresh: bool = False) -> tuple[Path, ...]:
    """Extract all files beside a ZIP, inside a folder named after the archive.

    Keep the ZIP and preserve relative paths beneath zip_path.parent / zip_path.stem.
    Directory-only entries are skipped; archives without files are rejected.

    With refresh=False, reuse extracted files whose sizes match archive metadata.
    With refresh=True, extract into a fresh temporary directory, then replace the
    previous extraction directory, including same-size files and obsolete members.
    If extraction fails, the previous directory remains untouched. Publication
    uses two renames, with rollback attempted if the second rename fails.
    The download script passes refresh=True even for same-day reruns.

    Return final extracted file paths in archive order. This function does not
    download the archive or convert extracted files into register inputs.
    """
    archive_path = Path(zip_path)
    with ZipFile(archive_path, "r") as archive:
        member_names = tuple(
            member.filename for member in archive.infolist() if not member.is_dir()
        )
    if not refresh:
        return extract_zip_members(archive_path, member_names, dest_dir=archive_path.parent)

    destination = archive_path.parent / archive_path.stem
    if destination.is_symlink() or destination.is_junction():
        raise ValueError(f"Extraction directory must not be a link: {destination}")
    with TemporaryDirectory(dir=archive_path.parent, prefix=".ex-") as staging:
        staging_dir = Path(staging)
        staged_paths = extract_zip_members(archive_path, member_names, dest_dir=staging_dir)
        staged_directory = staging_dir / archive_path.stem
        relative_paths = tuple(path.relative_to(staged_directory) for path in staged_paths)
        backup = staging_dir / "previous"
        # Keep the backup separate even if the archive is named previous.zip.
        if backup == staged_directory:
            backup = staging_dir / "previous-backup"
        had_previous = destination.exists()
        if had_previous:
            destination.rename(backup)
        try:
            staged_directory.rename(destination)
        except OSError:
            if had_previous:
                backup.rename(destination)
            raise
    return tuple(destination / path for path in relative_paths)


def _single_file_member(archive: ZipFile) -> ZipInfo:
    members = [member for member in archive.infolist() if not member.is_dir()]
    if len(members) != 1:
        expectation = "Expected exactly one non-directory member in ZIP archive"
        raise ValueError(f"{expectation}; found {len(members)}")
    return members[0]


def _safe_member_basename(member: ZipInfo) -> str:
    member_name = member.filename
    if (
        not member_name
        or member_name in {".", ".."}
        or "\x00" in member_name
        or PurePosixPath(member_name).name != member_name
        or PureWindowsPath(member_name).name != member_name
    ):
        raise ValueError(f"ZIP member must have a safe basename: {member_name!r}")
    _validate_regular_file(member)
    return member_name


def _unique_archive_members(archive: ZipFile) -> dict[str, ZipInfo]:
    members: dict[str, ZipInfo] = {}
    duplicate_names: set[str] = set()
    for member in archive.infolist():
        if member.filename in members:
            duplicate_names.add(member.filename)
        members[member.filename] = member

    if duplicate_names:
        duplicates = ", ".join(sorted(duplicate_names))
        raise ValueError(f"ZIP archive contains duplicate member names: {duplicates}")
    return members


def _safe_relative_path(member_name: str) -> Path:
    path_parts = member_name.split("/")
    windows_path = PureWindowsPath(member_name)
    if (
        not member_name
        or "\x00" in member_name
        or "\\" in member_name
        or PurePosixPath(member_name).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or any(part in {"", ".", ".."} for part in path_parts)
        or any(isreserved(part) for part in path_parts)
    ):
        raise ValueError(f"ZIP member must be a safe relative path: {member_name!r}")
    return Path(*path_parts)


def _validate_regular_file(member: ZipInfo) -> None:
    if member.is_dir():
        raise ValueError(f"ZIP member must be a regular file: {member.filename!r}")

    unix_file_type = S_IFMT(member.external_attr >> 16)
    if member.create_system == _UNIX_CREATE_SYSTEM and unix_file_type not in {
        0,
        S_IFREG,
    }:
        raise ValueError(f"ZIP member must be a regular file: {member.filename!r}")


def _extract_member(
    archive: ZipFile,
    member: ZipInfo,
    extract_dir: Path,
    relative_path: Path,
) -> Path:
    extracted_path = extract_dir / relative_path
    _reject_symlink_ancestors(extract_dir, extracted_path.parent)

    if (
        extracted_path.is_file()
        and not extracted_path.is_symlink()
        and extracted_path.stat().st_size == member.file_size
    ):
        logger.debug("Using cached extracted data at %s", extracted_path)
        return extracted_path

    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        dir=extracted_path.parent,
        prefix=".ex-",
    ) as temporary_dir:
        # Short temporary names avoid repeating long archive member filenames
        # inside an already deeply nested Windows path.
        temporary_path = Path(temporary_dir) / "data.part"
        with (
            archive.open(member, "r") as source,
            temporary_path.open("wb") as temporary_file,
        ):
            copyfileobj(source, temporary_file, _COPY_BUFFER_SIZE)

        if temporary_path.stat().st_size != member.file_size:
            raise OSError("Extracted file size does not match the ZIP archive metadata")
        _ = temporary_path.replace(extracted_path)

    logger.debug("Extracted data to %s", extracted_path)
    return extracted_path


def _reject_symlink_ancestors(extract_dir: Path, parent: Path) -> None:
    current = parent
    while current != extract_dir:
        if current.is_symlink():
            raise ValueError(f"Extraction path contains a symlink: {current}")
        current = current.parent
    if extract_dir.is_symlink():
        raise ValueError(f"Extraction path contains a symlink: {extract_dir}")


_CHUNK_SIZE = 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 300


def download_file(
    url: str,
    dest_dir: Path,
    *,
    filename: str | None = None,
    refresh: bool = False,
) -> Path:
    """Download a file with optional cache reuse and atomic file replacement.

    By default, reuse an existing regular destination file without a network
    request. With refresh=True, fetch it again even if it already exists; only
    replace the destination after the response has been written successfully.
    A failed download leaves the previous file intact. Extraction is a separate
    call to extract_zip; scripts/download_and_extract.py performs both with refresh=True.

    Parameters
    ----------
    url : str
        URL of the file to download.
    dest_dir : Path
        Explicit destination directory.
    filename : str, optional
        Local filename. Defaults to the decoded filename in the URL path.
    refresh : bool, optional
        Defaults to False. Set True to download again and replace an existing file.

    Returns
    -------
    Path
        Path to the downloaded or cached file.

    """
    destination_dir = dest_dir
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
    if not refresh and destination_path.is_file() and not destination_path.is_symlink():
        logger.info("Using cached data at %s", destination_path)
        return destination_path

    with TemporaryDirectory(
        dir=destination_dir,
        prefix=".dl-",
    ) as temporary_dir:
        temporary_path = Path(temporary_dir) / "data.part"
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
