"""Cached, atomic extraction for selected ZIP archive members."""

from logging import getLogger
from ntpath import isreserved
from pathlib import Path, PurePosixPath, PureWindowsPath
from shutil import copyfileobj
from stat import S_IFMT, S_IFREG
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from zipfile import ZipFile, ZipInfo

from uk_charity_local_authority_analysis.core.datasets.constants import (
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
) -> Path:
    """Extract the sole file in a ZIP archive using an atomic write.

    A cached file is reused when its size matches the uncompressed size
    recorded in the archive.

    Parameters
    ----------
    zip_path : str or Path
        ZIP archive containing exactly one non-directory member.
    dest_dir : Path, optional
        Parent directory for the archive-named extraction directory.
        Defaults to the shared staging directory.

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
        logger.info("Using cached extracted data at %s", extracted_path)
        return extracted_path

    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        dir=extracted_path.parent,
        prefix=f".{extracted_path.name}.",
    ) as temporary_dir:
        temporary_path = Path(temporary_dir) / f"{extracted_path.name}.part"
        with (
            archive.open(member, "r") as source,
            temporary_path.open("wb") as temporary_file,
        ):
            copyfileobj(source, temporary_file, _COPY_BUFFER_SIZE)

        if temporary_path.stat().st_size != member.file_size:
            raise OSError("Extracted file size does not match the ZIP archive metadata")
        _ = temporary_path.replace(extracted_path)

    logger.info("Extracted data to %s", extracted_path)
    return extracted_path


def _reject_symlink_ancestors(extract_dir: Path, parent: Path) -> None:
    current = parent
    while current != extract_dir:
        if current.is_symlink():
            raise ValueError(f"Extraction path contains a symlink: {current}")
        current = current.parent
    if extract_dir.is_symlink():
        raise ValueError(f"Extraction path contains a symlink: {extract_dir}")
