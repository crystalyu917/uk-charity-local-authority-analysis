"""Enrich a project-local charity register with 2022 UTLA codes and names."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import os

import polars as pl


def _postcode(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.String).str.strip_chars().str.to_uppercase().str.replace_all(r"\s+", "")


def prepare_charity_asset_register(
    charity_filepath: Path, lookup_filepath: Path, columns_to_keep: list[str] | None = None,
) -> pl.LazyFrame:
    """Left-join UTLA codes and names, retaining rows with unmatched postcodes.

    UTLA is the lookup's utla22cd code; UTLA_NAME is its utla22nm name. Duplicate lookup
    pairs are collapsed; conflicting codes for a postcode fail join validation.
    None keeps every source column plus UTLA and UTLA_NAME. A list selects columns in
    that order. The source register is never modified.
    """
    charities = pl.scan_parquet(charity_filepath)
    if {"UTLA", "UTLA_NAME"}.intersection(charities.collect_schema().names()):
        raise ValueError("The input already has UTLA columns; select the original charity register.")
    lookup = (
        pl.scan_csv(lookup_filepath, infer_schema=False)
        .select(
            _postcode("pcds").alias("_utla_postcode"),
            pl.col("utla22cd").alias("UTLA"),
            pl.col("utla22nm").alias("UTLA_NAME"),
        )
        .filter(pl.col("_utla_postcode").is_not_null() & (pl.col("_utla_postcode") != ""))
        .unique()
    )
    result = (
        charities.with_columns(_postcode("charity_postcode").alias("_utla_postcode"))
        .join(lookup, on="_utla_postcode", how="left", validate="m:1", maintain_order="left")
        .drop("_utla_postcode")
    )
    return result if columns_to_keep is None else result.select(columns_to_keep)


def build_charity_asset_register(
    charity_filepath: Path, lookup_filepath: Path, output_path: Path,
    columns_to_keep: list[str] | None = None,
) -> Path:
    """Publish a timestamped Parquet, preserving previous runs and source files."""
    run_time = datetime.now(timezone.utc)
    result = prepare_charity_asset_register(charity_filepath, lookup_filepath, columns_to_keep)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_path.parent, prefix=".asset-") as staging:
        temporary = Path(staging) / "register.parquet"
        result.sink_parquet(temporary)
        while True:
            timestamp = run_time.strftime("%Y%m%d_%H%M%S_%fZ")
            destination = output_path.with_name(f"{output_path.stem}_{timestamp}{output_path.suffix}")
            try:
                os.link(temporary, destination)
            except FileExistsError:
                run_time += timedelta(microseconds=1)
                continue
            return destination
