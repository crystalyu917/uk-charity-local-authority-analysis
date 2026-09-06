"""Lazy preparation of local-authority capital receipts."""

from pathlib import Path
from typing import Final

import polars as pl

from uk_charity_local_authority_analysis.council_asset_sales.datasets.la_capital_receipts import (
    FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN,
    scan_la_capital_receipts,
)
from uk_charity_local_authority_analysis.council_asset_sales.preprocessing.geography import (
    harmonise_lad25_codes,
)

_LAD_OWN_RECEIPT_CLASSES: Final = ("LB", "MD", "SD", "UA")
_REQUIRED_COLUMNS: Final = (
    "PeriodCode",
    "LA_LGF_Code",
    "ONS_Code",
    "LA_Name",
    "LA_Class",
    "LA_Subclass",
    "Status",
    FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN,
)
_PERIOD_CODE_FORMAT: Final = "%Y03"


def prepare_capital_receipts(
    capital_receipts: pl.LazyFrame,
) -> pl.LazyFrame:
    """Prepare submitted LAD-own fixed-asset disposal receipts at LAD25/year grain.

    The output retains only LB, MD, SD, and UA records. Shire-county and
    special-authority receipts are deliberately excluded, so predecessor
    district sums do not represent like-for-like unitary service coverage.
    ``financial_year`` is the April-start financial year's first calendar
    year. Source values remain in GBP thousands, with an explicit GBP millions
    derivative.
    """
    _require_columns(capital_receipts, _REQUIRED_COLUMNS)

    submitted_lads = (
        capital_receipts.filter(
            pl.col("Status").str.strip_chars().str.to_lowercase() == "submitted"
        )
        .filter(
            pl.col("LA_Class")
            .str.strip_chars()
            .str.to_uppercase()
            .is_in(_LAD_OWN_RECEIPT_CLASSES)
        )
        .select(
            pl.col("PeriodCode").cast(pl.Int32).alias("period_code"),
            pl.col("LA_LGF_Code")
            .cast(pl.String)
            .str.strip_chars()
            .alias("local_government_finance_code"),
            pl.col("ONS_Code")
            .cast(pl.String)
            .str.strip_chars()
            .alias("source_local_authority_code"),
            pl.col("LA_Name")
            .cast(pl.String)
            .str.strip_chars()
            .alias("source_local_authority"),
            pl.col("LA_Class")
            .cast(pl.String)
            .str.strip_chars()
            .str.to_uppercase()
            .alias("source_local_authority_class"),
            pl.col("LA_Subclass")
            .cast(pl.String)
            .str.strip_chars()
            .alias("source_local_authority_subclass"),
            pl.col("Status")
            .cast(pl.String)
            .str.strip_chars()
            .str.to_lowercase()
            .alias("source_status"),
            pl.col(FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN)
            .cast(pl.Int64)
            .alias("capital_receipts_gbp_thousands"),
        )
        .with_columns(
            _financial_year().alias("financial_year"),
            pl.col("source_local_authority_code").alias("local_authority_code"),
        )
        .pipe(harmonise_lad25_codes)
    )

    source_record = (
        pl.struct(
            "period_code",
            "local_government_finance_code",
            pl.col("source_local_authority_code").alias("local_authority_code"),
            pl.col("source_local_authority").alias("local_authority"),
            pl.col("source_local_authority_class").alias("local_authority_class"),
            pl.col("source_local_authority_subclass").alias("local_authority_subclass"),
            pl.col("source_status").alias("status"),
            "capital_receipts_gbp_thousands",
        )
        .sort_by("source_local_authority_code")
        .alias("capital_receipts_sources")
    )
    return (
        submitted_lads.group_by("financial_year", "local_authority_code")
        .agg(
            pl.col("capital_receipts_gbp_thousands").sum(),
            source_record,
        )
        .with_columns(
            (pl.col("capital_receipts_gbp_thousands").cast(pl.Float64) / 1_000).alias(
                "capital_receipts_gbp_millions"
            )
        )
        .select(
            "financial_year",
            "local_authority_code",
            "capital_receipts_gbp_thousands",
            "capital_receipts_gbp_millions",
            "capital_receipts_sources",
        )
        .sort("financial_year", "local_authority_code")
    )


def scan_capital_receipts(dest_dir: Path | None = None) -> pl.LazyFrame:
    """Build the prepared capital-receipts query without materialising it."""
    return prepare_capital_receipts(scan_la_capital_receipts(dest_dir))


def load_capital_receipts(dest_dir: Path | None = None) -> pl.DataFrame:
    """Materialise the prepared capital-receipts dataset."""
    return scan_capital_receipts(dest_dir).collect(engine="streaming")


def _financial_year() -> pl.Expr:
    period_end = (
        pl.col("period_code")
        .cast(pl.String)
        .fill_null("invalid")
        .str.strptime(pl.Date, _PERIOD_CODE_FORMAT, strict=True)
    )
    return (period_end.dt.year() - 1).cast(pl.Int32)


def _require_columns(frame: pl.LazyFrame, required: tuple[str, ...]) -> None:
    columns = set(frame.collect_schema().names())
    missing = sorted(set(required) - columns)
    if missing:
        raise ValueError(f"Missing required capital receipts columns: {missing}")
