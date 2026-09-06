"""Download, selectively extract, and load the ONS Postcode Directory.

Source:
    https://geoportal.statistics.gov.uk/datasets/6fff67d204fd4f339591ed667a6e3642/about
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from zipfile import ZipFile

import polars as pl

from uk_charity_local_authority_analysis.core.datasets.constants import PROJECT_ROOT
from uk_charity_local_authority_analysis.core.datasets.download import download_file
from uk_charity_local_authority_analysis.core.datasets.extraction import (
    extract_zip_members,
)
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup.endpoint import (
    ONS_POSTCODE_LOOKUP_FILENAME,
    ONS_POSTCODE_LOOKUP_URL,
)
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup.schema import (
    ONS_POSTCODE_LOOKUP_SCHEMA,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_MAIN_POSTCODE_COLUMN = "pcds"
_MAIN_LAD_CODE_PATTERN = re.compile(r"lad\d{2}cd", re.IGNORECASE)
_MAIN_REGION_CODE_PATTERN = re.compile(r"rgn\d{2}cd", re.IGNORECASE)
_LOOKUP_LAD_CODE_PATTERN = re.compile(r"LAD\d{2}CD")
_LOOKUP_LAD_NAME_PATTERN = re.compile(r"LAD\d{2}NM")
_LOOKUP_REGION_CODE_PATTERN = re.compile(r"RGN\d{2}CD")
_LOOKUP_REGION_NAME_PATTERN = re.compile(r"RGN\d{2}NM")
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "core" / "ons" / "raw"
DEFAULT_OUTPUT_PATH = DEFAULT_RAW_DIR / "ons_postcode_lookup.parquet"


@dataclass(frozen=True, slots=True)
class OnsPostcodeLookupFiles:
    """Paths to the three selectively extracted source CSV files."""

    postcode: Path
    lad: Path
    region: Path


def download_ons_postcode_lookup(dest_dir: Path | None = None) -> Path:
    """Download the ONS Postcode Directory ZIP unless it is cached."""
    return download_file(
        ONS_POSTCODE_LOOKUP_URL,
        dest_dir=dest_dir or DEFAULT_RAW_DIR,
        filename=ONS_POSTCODE_LOOKUP_FILENAME,
    )


def extract_ons_postcode_lookup(
    dest_dir: Path | None = None,
) -> OnsPostcodeLookupFiles:
    """Download and extract only the postcode, LAD, and region CSVs."""
    archive_path = download_ons_postcode_lookup(dest_dir=dest_dir)
    member_names = _find_source_members(archive_path)
    postcode_path, lad_path, region_path = extract_zip_members(
        archive_path,
        member_names,
        dest_dir=dest_dir or DEFAULT_RAW_DIR,
    )
    return OnsPostcodeLookupFiles(
        postcode=postcode_path,
        lad=lad_path,
        region=region_path,
    )


def scan_ons_postcode_lookup(dest_dir: Path | None = None) -> pl.LazyFrame:
    """Build a lazy postcode scan enriched with LAD and region names."""
    source_files = extract_ons_postcode_lookup(dest_dir=dest_dir)
    postcode_columns = _read_csv_columns(source_files.postcode, "postcodes")
    lad_columns = _read_csv_columns(source_files.lad, "LAD lookup")
    region_columns = _read_csv_columns(source_files.region, "region lookup")

    postcode_column = _require_column(
        postcode_columns,
        _MAIN_POSTCODE_COLUMN,
        "postcode",
    )
    lad_code_column = _require_pattern_column(
        postcode_columns,
        _MAIN_LAD_CODE_PATTERN,
        "LAD code",
    )
    region_code_column = _require_pattern_column(
        postcode_columns,
        _MAIN_REGION_CODE_PATTERN,
        "region code",
    )
    lookup_lad_code_column = _require_pattern_column(
        lad_columns,
        _LOOKUP_LAD_CODE_PATTERN,
        "LAD lookup code",
    )
    lookup_lad_name_column = _require_pattern_column(
        lad_columns,
        _LOOKUP_LAD_NAME_PATTERN,
        "LAD lookup name",
    )
    lookup_region_code_column = _require_pattern_column(
        region_columns,
        _LOOKUP_REGION_CODE_PATTERN,
        "region lookup code",
    )
    lookup_region_name_column = _require_pattern_column(
        region_columns,
        _LOOKUP_REGION_NAME_PATTERN,
        "region lookup name",
    )
    _validate_lookup_vintage(
        lad_code_column,
        lookup_lad_code_column,
        lookup_lad_name_column,
        "LAD",
    )
    _validate_lookup_vintage(
        region_code_column,
        lookup_region_code_column,
        lookup_region_name_column,
        "region",
    )

    postcodes = pl.scan_csv(
        source_files.postcode,
        infer_schema=False,
        low_memory=True,
    ).select(
        pl.col(postcode_column).alias("_pcd"),
        pl.col(lad_code_column).alias("_lad_code"),
        pl.col(region_code_column).alias("_region_code"),
    )
    lad_lookup = pl.scan_csv(
        source_files.lad,
        infer_schema=False,
    ).select(
        pl.col(lookup_lad_code_column).alias("_lad_lookup_code"),
        pl.col(lookup_lad_name_column).alias("_lad_name"),
    )
    region_lookup = pl.scan_csv(
        source_files.region,
        infer_schema=False,
    ).select(
        pl.col(lookup_region_code_column).alias("_region_lookup_code"),
        pl.col(lookup_region_name_column).alias("_region_name"),
    )

    return (
        postcodes.join(
            lad_lookup,
            left_on="_lad_code",
            right_on="_lad_lookup_code",
            how="left",
            validate="m:1",
        )
        .join(
            region_lookup,
            left_on="_region_code",
            right_on="_region_lookup_code",
            how="left",
            validate="m:1",
        )
        .select(
            pl.col("_pcd").alias("pcd"),
            pl.struct(
                pl.col("_lad_code").alias("code"),
                pl.col("_lad_name").alias("name"),
            ).alias("lad"),
            pl.struct(
                pl.col("_region_code").alias("code"),
                pl.col("_region_name").alias("name"),
            ).alias("region"),
        )
        .cast(ONS_POSTCODE_LOOKUP_SCHEMA)
    )


def load_ons_postcode_lookup(dest_dir: Path | None = None) -> pl.DataFrame:
    """Load the complete enriched postcode lookup into memory."""
    return scan_ons_postcode_lookup(dest_dir).collect(engine="streaming")


def build_ons_postcode_lookup(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    source_csv: Path | None = None,
) -> Path:
    """Create or reuse the compact core Parquet postcode lookup.

    An explicitly supplied CSV must exist. Without one, an existing output is
    reused, then a standalone CSV in the core raw directory is preferred. On a
    clean checkout the official archive is downloaded and its geography lookup
    files are joined before the Parquet output is written.
    """
    source = source_csv or DEFAULT_RAW_DIR / "onspd_may_2026_uk.csv"
    if source_csv is not None and not source.exists():
        raise FileNotFoundError(f"ONS postcode CSV was not found: {source}")

    if source_csv is None and output_path.is_file():
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        _write_lookup(scan_ons_postcode_lookup(dest_dir=DEFAULT_RAW_DIR), output_path)
        return output_path

    columns = _read_csv_columns(source, "postcodes")
    postcode_column = _require_column(columns, _MAIN_POSTCODE_COLUMN, "postcode")
    lad_column = _require_pattern_column(columns, _MAIN_LAD_CODE_PATTERN, "LAD code")
    region_column = _require_pattern_column(
        columns, _MAIN_REGION_CODE_PATTERN, "region code"
    )
    lookup = (
        pl.scan_csv(source, infer_schema=False, low_memory=True)
        .select(
            pl.col(postcode_column).alias("pcd"),
            pl.struct(
                pl.col(lad_column).alias("code"),
                pl.lit(None, dtype=pl.String).alias("name"),
            ).alias("lad"),
            pl.struct(
                pl.col(region_column).alias("code"),
                pl.lit(None, dtype=pl.String).alias("name"),
            ).alias("region"),
        )
        .cast(ONS_POSTCODE_LOOKUP_SCHEMA)
    )
    _write_lookup(lookup, output_path)
    return output_path


def _write_lookup(lookup: pl.LazyFrame, output_path: Path) -> None:
    """Only publish a completed Parquet file, since subsequent builds reuse it."""
    with TemporaryDirectory(dir=output_path.parent, prefix=".ons-lookup-") as directory:
        temporary_path = Path(directory) / output_path.name
        lookup.sink_parquet(temporary_path)
        temporary_path.replace(output_path)


def _find_source_members(archive_path: Path) -> tuple[str, str, str]:
    with ZipFile(archive_path, "r") as archive:
        member_paths = [
            PurePosixPath(member.filename)
            for member in archive.infolist()
            if not member.is_dir()
        ]

    postcode_member = _require_archive_member(
        [
            path
            for path in member_paths
            if path.parent == PurePosixPath("Data")
            and path.name.startswith("ONSPD_")
            and path.name.endswith("_UK.csv")
        ],
        "combined postcode CSV",
    )
    lad_member = _require_archive_member(
        [
            path
            for path in member_paths
            if path.parent == PurePosixPath("Documents")
            and path.name.startswith("LAD Local Authority District names and codes UK ")
            and path.suffix.casefold() == ".csv"
        ],
        "LAD names and codes CSV",
    )
    region_member = _require_archive_member(
        [
            path
            for path in member_paths
            if path.parent == PurePosixPath("Documents")
            and path.name.startswith("RGN Region names and codes EN ")
            and path.suffix.casefold() == ".csv"
        ],
        "region names and codes CSV",
    )
    return str(postcode_member), str(lad_member), str(region_member)


def _require_archive_member(
    matches: Sequence[PurePosixPath],
    description: str,
) -> PurePosixPath:
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {description} in ONS archive; found {len(matches)}"
        )
    return matches[0]


def _read_csv_columns(data_path: Path, description: str) -> tuple[str, ...]:
    with data_path.open(encoding="utf-8-sig", newline="") as data_file:
        try:
            columns = tuple(next(csv.reader(data_file)))
        except StopIteration as error:
            raise ValueError(f"ONS {description} CSV is empty") from error

    if len(set(columns)) != len(columns):
        raise ValueError(f"ONS {description} CSV contains duplicate columns")
    return columns


def _require_column(
    columns: Sequence[str],
    expected_column: str,
    description: str,
) -> str:
    if expected_column not in columns:
        raise ValueError(f"ONS {description} column was not found: {expected_column}")
    return expected_column


def _require_pattern_column(
    columns: Sequence[str],
    pattern: re.Pattern[str],
    description: str,
) -> str:
    matches = [column for column in columns if pattern.fullmatch(column)]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one ONS {description} column; found {len(matches)}"
        )
    return matches[0]


def _validate_lookup_vintage(
    source_code_column: str,
    lookup_code_column: str,
    lookup_name_column: str,
    description: str,
) -> None:
    expected_code_column = source_code_column.upper()
    expected_name_column = f"{expected_code_column.removesuffix('CD')}NM"
    if (
        lookup_code_column.upper() != expected_code_column
        or lookup_name_column.upper() != expected_name_column
    ):
        raise ValueError(
            f"ONS {description} lookup columns do not match the main geography "
            f"vintage: expected {expected_code_column} and {expected_name_column}"
        )
