"""Download and load the configured local authority capital receipts CSV."""

import csv
from pathlib import Path

import polars as pl

from uk_charity_local_authority_analysis.council_asset_sales import config
from uk_charity_local_authority_analysis.core.datasets.download import download_file
from uk_charity_local_authority_analysis.council_asset_sales.datasets.la_capital_receipts.schema import (
    build_la_capital_receipts_schema,
)

def download_la_capital_receipts(dest_dir: Path | None = None) -> Path:
    """Download the time series CSV unless it is already cached."""
    return download_file(
        config.COUNCIL_RECEIPTS_URL,
        dest_dir=dest_dir if dest_dir is not None else config.COUNCIL_RECEIPTS_PATH.parent,
        filename=config.COUNCIL_RECEIPTS_PATH.name,
    )


def scan_la_capital_receipts(dest_dir: Path | None = None) -> pl.LazyFrame:
    """Build a schema-controlled lazy scan of the time series CSV."""
    data_path = download_la_capital_receipts(dest_dir=dest_dir)
    column_names = _read_csv_columns(data_path)
    schema = build_la_capital_receipts_schema(column_names)
    return pl.scan_csv(data_path, schema=schema)


def load_la_capital_receipts(dest_dir: Path | None = None) -> pl.DataFrame:
    """Load the time series CSV into a schema-controlled Polars DataFrame."""
    return scan_la_capital_receipts(dest_dir).collect(engine="streaming")


def _read_csv_columns(data_path: Path) -> list[str]:
    with data_path.open(encoding="utf-8-sig", newline="") as data_file:
        try:
            return next(csv.reader(data_file))
        except StopIteration as error:
            raise ValueError("Local authority capital receipts CSV is empty") from error
