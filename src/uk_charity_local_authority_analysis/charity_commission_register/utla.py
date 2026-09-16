"""November 2023 postcode matching to 2022 upper-tier local authorities."""

from datetime import datetime
from pathlib import Path

import polars as pl

from uk_charity_local_authority_analysis.charity_commission_register.config import UTLA_CSV_FILENAME
from uk_charity_local_authority_analysis.charity_commission_register.filepath import (
    UTLA_LOOKUP_DIR, UTLA_LOOKUP_FILEPATH,
)


def latest_utla_lookup(directory: Path = UTLA_LOOKUP_DIR) -> Path:
    """Select the lookup in the newest dated download folder, including subfolders."""
    candidates = []
    for folder in directory.glob("*"):
        if not folder.is_dir() or len(folder.name) != 8 or not folder.name.isdigit():
            continue
        try:
            downloaded = datetime.strptime(folder.name, "%d%m%Y")
        except ValueError:
            continue
        for path in folder.rglob(UTLA_CSV_FILENAME):
            if path.is_file():
                candidates.append((downloaded, path))
    if not candidates:
        raise FileNotFoundError(
            f"UTLA lookup missing in {directory}. Run scripts/download_and_extract.py utla first."
        )
    newest = max(downloaded for downloaded, _ in candidates)
    matches = [path for downloaded, path in candidates if downloaded == newest]
    if len(matches) != 1:
        raise ValueError("Multiple UTLA CSVs in the newest download; specify utla_filepath explicitly.")
    return matches[0]


def load_utla(filepath: Path = UTLA_LOOKUP_FILEPATH) -> pl.DataFrame:
    """Read only the postcode, authority code and name from a local lookup."""
    if not filepath.is_file():
        raise FileNotFoundError(
            f"UTLA lookup missing: {filepath}. Run scripts/download_and_extract.py utla first."
        )
    return pl.read_csv(filepath, columns=["pcds", "utla22cd", "utla22nm"], infer_schema=False)


def _postcode(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.String).str.to_uppercase().str.replace_all(r"\s+", "")


def add_utla(charities: pl.DataFrame, utla: pl.DataFrame) -> pl.DataFrame:
    """Append UTLA and UTLA_name, preserving rows, order and original postcodes.

    Identical mappings collapse; conflicting mappings fail the many-to-one join.
    Blank and missing lookup postcodes never match. Unmatched rows retain nulls.
    """
    if {"UTLA", "UTLA_name", "_utla_postcode"}.intersection(charities.columns):
        raise ValueError("The input already has UTLA columns or the reserved _utla_postcode column.")
    lookup = (
        utla.select(
            _postcode("pcds").alias("_utla_postcode"),
            pl.col("utla22cd").cast(pl.String).alias("UTLA"),
            pl.col("utla22nm").cast(pl.String).alias("UTLA_name"),
        )
        .filter(pl.col("_utla_postcode").is_not_null() & (pl.col("_utla_postcode") != ""))
        .unique()
    )
    return (
        charities.with_columns(_postcode("charity_postcode").alias("_utla_postcode"))
        .join(lookup, on="_utla_postcode", how="left", validate="m:1", maintain_order="left")
        .drop("_utla_postcode")
    )
