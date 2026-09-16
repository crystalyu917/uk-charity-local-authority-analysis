"""Build an England and Wales charity register from the local source snapshots."""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl

from uk_charity_local_authority_analysis.charity_commission_register.charity_commission import (
    clean_charity,
    clean_charity_classification,
    load_charity,
    load_charity_classification,
)
from uk_charity_local_authority_analysis.charity_commission_register.company_house import (
    _company_number_expr,
    clean_company_house,
    load_company_house,
)
from uk_charity_local_authority_analysis.charity_commission_register.config import (
    CATEGORY_MAPPING,
)
from uk_charity_local_authority_analysis.charity_commission_register.filepath import (
    CHARITY_CLASSIFICATION_FILEPATH,
    CHARITY_FILEPATH,
    CHARITY_REGISTER_FILEPATH,
    COMPANY_HOUSE_FILEPATH,
    FIND_THAT_CHARITY_FILEPATH,
    ONS_LOOKUP_FILEPATH,
    UTLA_LOOKUP_FILEPATH,
)
from uk_charity_local_authority_analysis.charity_commission_register.find_that_charity import (
    clean_find_that_charity,
    load_find_that_charity,
)
from uk_charity_local_authority_analysis.charity_commission_register.ons import (
    load_ons,
    make_postcode_to_local_authority_lookup,
)

from uk_charity_local_authority_analysis.charity_commission_register.utla import add_utla, load_utla

logger = getLogger(__name__)


def charity_address(df: pl.DataFrame) -> pl.DataFrame:
    # Convert empty string values to nulls
    postcode_cols = ["RegAddress.PostCode", "charity_contact_postcode", "postalCode"]
    df = df.with_columns(
        pl.when(
            pl.col(col)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_lowercase()
            .is_in(["", "nan", "none", "null"])
        )
        .then(None)
        .otherwise(pl.col(col).cast(pl.Utf8).str.strip_chars())
        .alias(col)
        for col in postcode_cols
        if col in df.columns
    )

    # Pick the first available non-null postcode
    available = [pl.col(col) for col in postcode_cols if col in df.columns]
    postcode = pl.coalesce(available) if available else pl.lit(None, dtype=pl.String)
    return df.with_columns(
        postcode.str.to_uppercase()
        .str.replace_all(r"\s+", "")
        .alias("charity_postcode")
    )


def merge_charity_data(
    charity: pl.DataFrame,
    charity_class: pl.DataFrame,
    company_house: pl.DataFrame,
    find_that_charity: pl.DataFrame,
    ons: pl.DataFrame,
    utla: pl.DataFrame,
) -> pl.DataFrame:
    """End-to-end processing and merging of all charity data."""
    charity = clean_charity(charity)
    charity_class = clean_charity_classification(charity_class)
    company_house = clean_company_house(company_house)
    find_that_charity = clean_find_that_charity(find_that_charity)
    la_lookup = make_postcode_to_local_authority_lookup(ons)

    df = (
        charity.join(
            charity_class, on="registered_charity_number", how="left", validate="1:1"
        )
        .join(
            company_house,
            left_on="charity_company_registration_number",
            right_on="CompanyNumber",
            how="left",
            validate="m:1",
        )
        .join(
            find_that_charity,
            on="registered_charity_number",
            how="left",
            validate="1:1",
        )
        .with_columns(pl.col(list(CATEGORY_MAPPING)).fill_null(0))
    )

    df = charity_address(df)
    df = df.join(la_lookup, on="charity_postcode", how="left", validate="m:1")

    return add_utla(df, utla)


def load_charity_register(
    charity: pl.DataFrame | None = None,
    charity_class: pl.DataFrame | None = None,
    company_house: pl.DataFrame | None = None,
    find_that_charity: pl.DataFrame | None = None,
    ons: pl.DataFrame | None = None,
    utla: pl.DataFrame | None = None,
    *,
    charity_filepath: Path = CHARITY_FILEPATH,
    classification_filepath: Path = CHARITY_CLASSIFICATION_FILEPATH,
    company_house_filepath: Path = COMPANY_HOUSE_FILEPATH,
    find_that_charity_filepath: Path = FIND_THAT_CHARITY_FILEPATH,
    ons_filepath: Path = ONS_LOOKUP_FILEPATH,
    utla_filepath: Path = UTLA_LOOKUP_FILEPATH,
) -> pl.DataFrame:
    """Load and merge all charity data."""
    if charity is None:
        charity = load_charity(charity_filepath)
    if charity_class is None:
        charity_class = load_charity_classification(classification_filepath)
    if company_house is None:
        logger.info("Loading Companies House records for charity company numbers")
        company_numbers = (
            charity.rename(lambda col: col.strip())
            .select(_company_number_expr("charity_company_registration_number"))
            .to_series()
        )
        company_house = load_company_house(
            company_numbers, filepath=company_house_filepath
        )
    if find_that_charity is None:
        find_that_charity = load_find_that_charity(find_that_charity_filepath)
    if ons is None:
        ons = load_ons(ons_filepath)
    if utla is None:
        utla = load_utla(utla_filepath)

    logger.info("Merging charity, classification, company, and postcode data")
    return merge_charity_data(
        charity,
        charity_class,
        company_house,
        find_that_charity,
        ons,
        utla,
    )


def build_charity_register(
    output_path: Path = CHARITY_REGISTER_FILEPATH,
    *,
    charity_filepath: Path = CHARITY_FILEPATH,
    classification_filepath: Path = CHARITY_CLASSIFICATION_FILEPATH,
    company_house_filepath: Path = COMPANY_HOUSE_FILEPATH,
    find_that_charity_filepath: Path = FIND_THAT_CHARITY_FILEPATH,
    ons_filepath: Path = ONS_LOOKUP_FILEPATH,
    utla_filepath: Path = UTLA_LOOKUP_FILEPATH,
) -> Path:
    """Build from explicit CSV/ONS/UTLA inputs and save a timestamped register.

    Omitted paths use filepath.py defaults. The ONS input must be a prepared
    Parquet lookup; scripts arrange any required download or preparation.
    UTLA input is the extracted postcode-to-UTLA CSV. A matching run record
    records the actual supplied input paths.
    """
    run_time = datetime.now(timezone.utc)
    started_at = run_time.isoformat()
    inputs = {
        name: _file_record(path)
        for name, path in {
            "charity_commission": charity_filepath,
            "charity_classification": classification_filepath,
            "companies_house": company_house_filepath,
            "find_that_charity": find_that_charity_filepath,
            "utla_lookup": utla_filepath,
        }.items()
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    register = load_charity_register(
        charity_filepath=charity_filepath,
        classification_filepath=classification_filepath,
        company_house_filepath=company_house_filepath,
        find_that_charity_filepath=find_that_charity_filepath,
        ons_filepath=ons_filepath,
        utla_filepath=utla_filepath,
    )
    inputs["ons_lookup"] = _file_record(ons_filepath)
    with TemporaryDirectory(
        dir=output_path.parent, prefix=".charity-register-"
    ) as directory:
        temporary_path = Path(directory) / output_path.name
        register.write_parquet(temporary_path)
        while True:
            timestamp = run_time.strftime("%Y%m%d_%H%M%S_%fZ")
            saved_path = output_path.with_name(
                f"{output_path.stem}_{timestamp}{output_path.suffix}"
            )
            record_path = saved_path.with_suffix(".run.json")
            record = {
                "schema_version": 1,
                "started_at_utc": started_at,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "inputs": inputs,
                "ons": {"mode": "local_parquet", "path": str(ons_filepath.resolve())},
                "output": {
                    "path": str(saved_path.resolve()),
                    "size_bytes": temporary_path.stat().st_size,
                    "rows": register.height,
                    "columns": register.width,
                },
            }
            temporary_record = Path(directory) / "run.json"
            temporary_record.write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )
            try:
                # Publish the completed file atomically without replacing any run.
                os.link(temporary_path, saved_path)
            except FileExistsError:
                run_time += timedelta(microseconds=1)
                continue
            try:
                os.link(temporary_record, record_path)
            except FileExistsError:
                saved_path.unlink()
                run_time += timedelta(microseconds=1)
                continue
            except OSError:
                saved_path.unlink()
                raise
            break
    logger.info("Wrote %s charities to %s", register.height, saved_path)
    logger.info("Run record: %s", record_path)
    return saved_path


def _file_record(path: Path) -> dict:
    """Record the selected file and its filesystem version without rereading it."""
    record = {"path": str(path.resolve()), "exists": path.is_file()}
    if record["exists"]:
        info = path.stat()
        record.update(size_bytes=info.st_size, modified_time_ns=info.st_mtime_ns)
    return record


def latest_charity_register(output_path: Path | None = None) -> Path:
    """Find the latest timestamped run, falling back to the old unsuffixed file."""
    base = output_path if output_path is not None else CHARITY_REGISTER_FILEPATH
    pattern = re.compile(
        rf"{re.escape(base.stem)}_\d{{8}}_\d{{6}}_\d{{6}}Z{re.escape(base.suffix)}"
    )
    runs = (
        [
            path
            for path in base.parent.iterdir()
            if path.is_file() and pattern.fullmatch(path.name)
        ]
        if base.parent.is_dir()
        else []
    )
    if runs:
        return max(runs, key=lambda path: path.name)
    if base.is_file():
        return base
    raise FileNotFoundError(
        f"No charity register found in {base.parent}; run the core build first"
    )


def scan_charity_removals(
    data_path: Path | None = None,
) -> pl.LazyFrame:
    """Aggregate removals from an explicit file or the latest saved run."""
    if data_path is None:
        data_path = latest_charity_register()
    return (
        pl.scan_parquet(data_path)
        .filter(
            pl.col("local_authority_code").is_not_null()
            & pl.col("removal_fy").is_not_null()
        )
        .with_columns(
            pl.col("local_authority_code").cast(pl.String).str.strip_chars(),
            pl.col("removal_fy").cast(pl.Int64).alias("financial_year"),
            pl.col("size_category").fill_null("Unknown").cast(pl.String),
        )
        .group_by("local_authority_code", "financial_year", "size_category")
        .agg(pl.len().cast(pl.Int64).alias("removals"))
    )
