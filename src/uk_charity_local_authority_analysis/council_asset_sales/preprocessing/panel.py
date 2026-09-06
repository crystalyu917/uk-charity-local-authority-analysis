"""Charity-removals and capital-receipts panel construction."""

from pathlib import Path
from typing import Final

import polars as pl

from uk_charity_local_authority_analysis.council_asset_sales import config
from uk_charity_local_authority_analysis.core.charity import (
    latest_charity_register,
    scan_charity_removals,
)
from uk_charity_local_authority_analysis.council_asset_sales.preprocessing.capital_receipts import (
    scan_capital_receipts,
)
from uk_charity_local_authority_analysis.council_asset_sales.preprocessing.geography import (
    prepare_current_english_lads,
)

_SIZE_CATEGORIES: Final = config.COUNCIL_SIZE_CATEGORIES
_PANEL_KEYS: Final = ("local_authority_code", "financial_year")
_REMOVAL_KEYS: Final = (*_PANEL_KEYS, "size_category")
_DEFAULT_START_YEAR: Final = config.COUNCIL_START_YEAR
_DEFAULT_END_YEAR: Final = config.COUNCIL_END_YEAR
_LAG_PERIODS: Final = config.COUNCIL_LAG_PERIODS
DEFAULT_OUTPUT_PATH = config.COUNCIL_PANEL_OUTPUT_PATH


def build_charity_receipts_panel(
    receipts: pl.LazyFrame,
    removals: pl.LazyFrame,
    current_lads: pl.LazyFrame,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pl.LazyFrame:
    """Build a balanced current-English-LAD charity-removals panel.

    Receipt lags use exact financial-year joins against the full receipt input,
    including observations before ``start_year``. Missing receipt observations
    remain null, while absent removal counts are known zeros. Receipt exposure
    is LAD-own rather than like-for-like full-service coverage across local
    government reorganisations. The panel retains the register's Small, Medium,
    and Large categories; separately prepared Unknown-size removals remain
    available from ``scan_charity_removals``.
    """
    if start_year is None:
        start_year = _DEFAULT_START_YEAR
    if end_year is None:
        end_year = _DEFAULT_END_YEAR

    if start_year > end_year:
        msg = "start_year must not be later than end_year"
        raise ValueError(msg)

    receipt_values = _select_receipt_values(receipts)
    receipt_names = _select_latest_receipt_names(receipts)
    lad_years = _select_current_lads(current_lads).join(
        receipt_names,
        on="local_authority_code",
        how="left",
        coalesce=True,
    ).with_columns(
        pl.coalesce("local_authority", "receipt_local_authority").alias(
            "local_authority"
        )
    ).drop("receipt_local_authority").join(
        _financial_years(start_year, end_year),
        how="cross",
    )
    panel = lad_years.join(
        receipt_values.with_columns(
            pl.lit(value=True).alias("receipt_observed"),
        ),
        on=_PANEL_KEYS,
        how="left",
        validate="1:1",
        coalesce=True,
    ).with_columns(pl.col("receipt_observed").fill_null(value=False))

    for lag in _LAG_PERIODS:
        lagged_receipts = receipt_values.select(
            "local_authority_code",
            (pl.col("financial_year") + lag).alias("financial_year"),
            pl.col("capital_receipts_gbp_millions").alias(
                f"capital_receipts_gbp_millions_lag{lag}"
            ),
        )
        panel = panel.join(
            lagged_receipts,
            on=_PANEL_KEYS,
            how="left",
            validate="1:1",
            coalesce=True,
        )

    size_categories = pl.DataFrame(
        {
            "size_category": _SIZE_CATEGORIES,
            "_size_order": range(len(_SIZE_CATEGORIES)),
        },
        schema_overrides={"_size_order": pl.Int8},
    ).lazy()
    prepared_removals = removals.select(
        pl.col("local_authority_code").cast(pl.String),
        pl.col("financial_year").cast(pl.Int64),
        pl.col("size_category").cast(pl.String),
        pl.col("removals").cast(pl.Int64),
    )

    return (
        panel.join(size_categories, how="cross")
        .join(
            prepared_removals,
            on=_REMOVAL_KEYS,
            how="left",
            validate="1:1",
            coalesce=True,
        )
        .with_columns(pl.col("removals").fill_null(0))
        .sort("local_authority_code", "financial_year", "_size_order")
        .select(
            "local_authority_code",
            "local_authority",
            "region_code",
            "region_name",
            "financial_year",
            "size_category",
            "capital_receipts_gbp_thousands",
            "capital_receipts_gbp_millions",
            "receipt_observed",
            *(f"capital_receipts_gbp_millions_lag{lag}" for lag in _LAG_PERIODS),
            "removals",
        )
    )


def scan_charity_receipts_panel(
    dest_dir: Path | None = None,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pl.LazyFrame:
    """Build the panel query from the cached or downloaded source datasets."""
    if start_year is None:
        start_year = _DEFAULT_START_YEAR
    if end_year is None:
        end_year = _DEFAULT_END_YEAR

    return build_charity_receipts_panel(
        scan_capital_receipts(dest_dir),
        scan_charity_removals(
            config.COUNCIL_CHARITY_PATH
            if config.COUNCIL_CHARITY_PATH is not None
            else latest_charity_register(config.COUNCIL_RAW_DIR / "charity_register.parquet")
        ),
        prepare_current_english_lads(pl.scan_parquet(config.COUNCIL_POSTCODE_LOOKUP_PATH)),
        start_year=start_year,
        end_year=end_year,
    )


def load_charity_receipts_panel(
    dest_dir: Path | None = None,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pl.DataFrame:
    """Materialise the charity-removals and capital-receipts panel."""
    if start_year is None:
        start_year = _DEFAULT_START_YEAR
    if end_year is None:
        end_year = _DEFAULT_END_YEAR

    return scan_charity_receipts_panel(
        dest_dir,
        start_year=start_year,
        end_year=end_year,
    ).collect(engine="streaming")


def write_charity_receipts_panel(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> Path:
    """Build the panel and write it to the council-asset-sales output directory."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scan_charity_receipts_panel(
        start_year=start_year,
        end_year=end_year,
    ).sink_parquet(output_path)
    return output_path


def _select_receipt_values(receipts: pl.LazyFrame) -> pl.LazyFrame:
    return receipts.select(
        pl.col("local_authority_code").cast(pl.String),
        pl.col("financial_year").cast(pl.Int64),
        pl.col("capital_receipts_gbp_thousands").cast(pl.Int64),
        pl.col("capital_receipts_gbp_millions").cast(pl.Float64),
    )


def _select_latest_receipt_names(receipts: pl.LazyFrame) -> pl.LazyFrame:
    """Select each LAD's latest submitted source name for display."""
    return (
        receipts.select(
            "local_authority_code",
            "financial_year",
            "capital_receipts_sources",
        )
        .explode("capital_receipts_sources")
        .select(
            pl.col("local_authority_code").cast(pl.String),
            pl.col("financial_year").cast(pl.Int64),
            pl.col("capital_receipts_sources")
            .struct.field("local_authority")
            .cast(pl.String)
            .str.strip_chars()
            .alias("receipt_local_authority"),
        )
        .filter(pl.col("receipt_local_authority").is_not_null())
        .sort("financial_year", descending=True)
        .unique("local_authority_code", keep="first", maintain_order=True)
        .select("local_authority_code", "receipt_local_authority")
    )


def _select_current_lads(current_lads: pl.LazyFrame) -> pl.LazyFrame:
    return current_lads.select(
        pl.col("local_authority_code").cast(pl.String),
        pl.col("local_authority").cast(pl.String),
        pl.col("region_code").cast(pl.String),
        pl.col("region_name").cast(pl.String),
    )


def _financial_years(start_year: int, end_year: int) -> pl.LazyFrame:
    return pl.DataFrame(
        {"financial_year": range(start_year, end_year + 1)},
        schema_overrides={"financial_year": pl.Int64},
    ).lazy()
