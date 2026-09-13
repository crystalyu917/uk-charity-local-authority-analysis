"""Charity-removals and capital-receipts panel construction."""

from pathlib import Path
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
import os
import re
from typing import Final

import polars as pl

from projects.council_asset_sales import config, filepath
from uk_charity_local_authority_analysis.charity_commission_register.build_charity_register import (
    latest_charity_register,
    scan_charity_removals,
)
from projects.council_asset_sales.pipeline.la_capital_receipts import (
    scan_la_capital_receipts,
)
from projects.council_asset_sales.pipeline.geography import (
    prepare_current_english_lads,
)

_CHARITY_SIZE_CATEGORIES: Final = config.CHARITY_SIZE_CATEGORIES
_PANEL_KEYS: Final = ("local_authority_code", "financial_year")
_CHARITY_REMOVAL_KEYS: Final = (*_PANEL_KEYS, "charity_size_category")
_DEFAULT_START_YEAR: Final = config.PANEL_START_YEAR
_DEFAULT_END_YEAR: Final = config.PANEL_END_YEAR
_LA_RECEIPTS_LAG_PERIODS: Final = config.LA_RECEIPTS_LAG_PERIODS
CHARITY_LA_RECEIPTS_PANEL_FILEPATH = filepath.CHARITY_LA_RECEIPTS_PANEL_FILEPATH


def build_charity_la_receipts_panel(
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
            pl.lit(value=True).alias("la_receipt_observed"),
        ),
        on=_PANEL_KEYS,
        how="left",
        validate="1:1",
        coalesce=True,
    ).with_columns(pl.col("la_receipt_observed").fill_null(value=False))

    for lag in _LA_RECEIPTS_LAG_PERIODS:
        lagged_receipts = receipt_values.select(
            "local_authority_code",
            (pl.col("financial_year") + lag).alias("financial_year"),
            pl.col("la_capital_receipts_gbp_millions").alias(
                f"la_capital_receipts_gbp_millions_lag{lag}"
            ),
        )
        panel = panel.join(
            lagged_receipts,
            on=_PANEL_KEYS,
            how="left",
            validate="1:1",
            coalesce=True,
        )

    charity_size_categories = pl.DataFrame(
        {
            "charity_size_category": _CHARITY_SIZE_CATEGORIES,
            "_charity_size_order": range(len(_CHARITY_SIZE_CATEGORIES)),
        },
        schema_overrides={"_charity_size_order": pl.Int8},
    ).lazy()
    prepared_removals = removals.select(
        pl.col("local_authority_code").cast(pl.String),
        pl.col("financial_year").cast(pl.Int64),
        pl.col("size_category").cast(pl.String).alias("charity_size_category"),
        pl.col("removals").cast(pl.Int64),
    )

    return (
        panel.join(charity_size_categories, how="cross")
        .join(
            prepared_removals,
            on=_CHARITY_REMOVAL_KEYS,
            how="left",
            validate="1:1",
            coalesce=True,
        )
        .with_columns(pl.col("removals").fill_null(0))
        .sort("local_authority_code", "financial_year", "_charity_size_order")
        .select(
            "local_authority_code",
            "local_authority",
            "region_code",
            "region_name",
            "financial_year",
            "charity_size_category",
            "la_capital_receipts_gbp_thousands",
            "la_capital_receipts_gbp_millions",
            "la_receipt_observed",
            *(f"la_capital_receipts_gbp_millions_lag{lag}" for lag in _LA_RECEIPTS_LAG_PERIODS),
            "removals",
        )
    )


def scan_charity_la_receipts_panel(
    dest_dir: Path | None = None,
    *,
    receipts_filepath: Path | None = None,
    charity_filepath: Path | None = None,
    ons_filepath: Path | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pl.LazyFrame:
    """Build the panel query from existing local source datasets."""
    if start_year is None:
        start_year = _DEFAULT_START_YEAR
    if end_year is None:
        end_year = _DEFAULT_END_YEAR

    selected_charity_filepath = charity_filepath
    if selected_charity_filepath is None:
        selected_charity_filepath = filepath.CHARITY_REGISTER_FILEPATH
    if selected_charity_filepath is None:
        selected_charity_filepath = latest_charity_register(filepath.CHARITY_REGISTER_BASE_FILEPATH)

    return build_charity_la_receipts_panel(
        scan_la_capital_receipts(dest_dir, input_filepath=receipts_filepath),
        scan_charity_removals(selected_charity_filepath),
        prepare_current_english_lads(pl.scan_parquet(
            ons_filepath if ons_filepath is not None else filepath.ONS_LOOKUP_FILEPATH
        )),
        start_year=start_year,
        end_year=end_year,
    )


def load_charity_la_receipts_panel(
    dest_dir: Path | None = None,
    *,
    receipts_filepath: Path | None = None,
    charity_filepath: Path | None = None,
    ons_filepath: Path | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pl.DataFrame:
    """Materialise the charity-removals and capital-receipts panel."""
    if start_year is None:
        start_year = _DEFAULT_START_YEAR
    if end_year is None:
        end_year = _DEFAULT_END_YEAR

    return scan_charity_la_receipts_panel(
        dest_dir,
        receipts_filepath=receipts_filepath,
        charity_filepath=charity_filepath,
        ons_filepath=ons_filepath,
        start_year=start_year,
        end_year=end_year,
    ).collect(engine="streaming")


def write_charity_la_receipts_panel(
    output_path: Path = CHARITY_LA_RECEIPTS_PANEL_FILEPATH,
    *,
    receipts_filepath: Path | None = None,
    charity_filepath: Path | None = None,
    ons_filepath: Path | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> Path:
    """Save a new panel with its UTC run date, time, and microseconds in the name."""
    run_time = datetime.now(timezone.utc)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel = scan_charity_la_receipts_panel(
        receipts_filepath=receipts_filepath,
        charity_filepath=charity_filepath,
        ons_filepath=ons_filepath,
        start_year=start_year,
        end_year=end_year,
    )
    with TemporaryDirectory(dir=output_path.parent, prefix=".panel-") as staging:
        temporary_path = Path(staging) / "panel.parquet"
        panel.sink_parquet(temporary_path)
        while True:
            timestamp = run_time.strftime("%Y%m%d_%H%M%S_%fZ")
            saved_path = output_path.with_name(f"{output_path.stem}_{timestamp}{output_path.suffix}")
            try:
                os.link(temporary_path, saved_path)
            except FileExistsError:
                run_time += timedelta(microseconds=1)
                continue
            return saved_path


def latest_charity_la_receipts_panel(output_path: Path = CHARITY_LA_RECEIPTS_PANEL_FILEPATH) -> Path:
    """Find the latest completed timestamped panel, falling back to the basename."""
    pattern = re.compile(rf"{re.escape(output_path.stem)}_\d{{8}}_\d{{6}}_\d{{6}}Z{re.escape(output_path.suffix)}")
    candidates = [path for path in output_path.parent.glob(f"{output_path.stem}_*{output_path.suffix}")
                  if path.is_file() and pattern.fullmatch(path.name)]
    if candidates:
        return max(candidates, key=lambda path: path.name)
    if output_path.is_file():
        return output_path
    raise FileNotFoundError(f"No panel found beside {output_path}. Run projects/council_asset_sales/scripts/build.py first.")


def _select_receipt_values(receipts: pl.LazyFrame) -> pl.LazyFrame:
    return receipts.select(
        pl.col("local_authority_code").cast(pl.String),
        pl.col("financial_year").cast(pl.Int64),
        pl.col("la_capital_receipts_gbp_thousands").cast(pl.Int64),
        pl.col("la_capital_receipts_gbp_millions").cast(pl.Float64),
    )


def _select_latest_receipt_names(receipts: pl.LazyFrame) -> pl.LazyFrame:
    """Select each LAD's latest submitted source name for display."""
    return (
        receipts.select(
            "local_authority_code",
            "financial_year",
            "la_capital_receipts_sources",
        )
        .explode("la_capital_receipts_sources")
        .select(
            pl.col("local_authority_code").cast(pl.String),
            pl.col("financial_year").cast(pl.Int64),
            pl.col("la_capital_receipts_sources")
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
