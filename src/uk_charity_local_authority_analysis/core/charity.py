"""Build an England and Wales charity register from the local source snapshots."""

from datetime import datetime, timedelta, timezone
from logging import getLogger
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl

from uk_charity_local_authority_analysis.core.config import (
    CHARITY,
    CHARITY_CLASSIFICATION,
    CHARITY_OUTPUT_PATH as DEFAULT_OUTPUT_PATH,
    COMPANY_HOUSE,
    FIND_THAT_CHARITY,
    ONS_OUTPUT_PATH as ONS,
)
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup.datasets import (
    build_ons_postcode_lookup,
)
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup import datasets as ons_datasets

logger = getLogger(__name__)

_SMALL_INCOME_LIMIT = 25_000
_MEDIUM_INCOME_LIMIT = 1_000_000

CATEGORY_MAPPING = {
    "Grantmaking_And_Financial_Support": [
        "classification_makes_grants_to_individuals",
        "classification_makes_grants_to_organisations",
        "classification_provides_other_finance",
    ],
    "Housing_And_Infrastructure": [
        "classification_accommodation/housing",
        "classification_provides_buildings/facilities/open_space",
    ],
    "Education_And_Research": [
        "classification_education/training",
        "classification_sponsors_or_undertakes_research",
    ],
    "Children_And_Youth": [
        "classification_children/young_people",
        "classification_amateur_sport",
    ],
    "Health_And_Disability": [
        "classification_the_advancement_of_health_or_saving_of_lives",
        "classification_disability",
        "classification_people_with_disabilities",
    ],
    "Advocacy_And_Human_Rights": [
        "classification_human_rights/religious_or_racial_harmony/equality_or_diversity",
        "classification_provides_advocacy/advice/information",
        "classification_people_of_a_particular_ethnic_or_racial_origin",
    ],
    "Religious_Activities": ["classification_religious_activities"],
    "Environment_And_Animals": [
        "classification_environment/conservation/heritage",
        "classification_animals",
    ],
    "Community_And_Social_Welfare": [
        "classification_economic/community_development/employment",
        "classification_general_charitable_purposes",
        "classification_the_prevention_or_relief_of_poverty",
        "classification_provides_services",
        "classification_other_charitable_activities",
        "classification_other_charitable_purposes",
    ],
    "Charity_Sector_Support": [
        "classification_acts_as_an_umbrella_or_resource_body",
        "classification_other_charities_or_voluntary_bodies",
        "classification_provides_human_resources",
    ],
    "International_And_Humanitarian": ["classification_overseas_aid/famine_relief"],
    "Elderly_Support": ["classification_elderly/old_people"],
    "General_Public_And_Misc": [
        "classification_the_general_public/mankind",
        "classification_other_defined_groups",
    ],
    "Arts_And_Recreation": [
        "classification_arts/culture/heritage/science",
        "classification_recreation",
    ],
    "Military_And_Civil_Efficiency": [
        "classification_armed_forces/emergency_service_efficiency",
    ],
}


def load_charity() -> pl.DataFrame:
    return pl.read_csv(CHARITY, infer_schema=False)


def load_charity_classification() -> pl.DataFrame:
    return pl.read_csv(CHARITY_CLASSIFICATION, infer_schema=False)


def load_company_house(company_numbers: pl.Series | None = None) -> pl.DataFrame:
    """Read company fields as strings, optionally retaining only needed companies."""
    companies = pl.scan_csv(
        COMPANY_HOUSE, infer_schema=False,
        with_column_names=lambda columns: [column.strip() for column in columns],
    ).with_columns(_company_number_expr("CompanyNumber"))
    if company_numbers is not None:
        companies = companies.filter(
            pl.col("CompanyNumber").is_in(company_numbers.drop_nulls().implode())
        )
    return companies.collect(engine="streaming")


def load_find_that_charity() -> pl.DataFrame:
    return pl.read_csv(
        FIND_THAT_CHARITY,
        infer_schema=False,
    )


def load_ons() -> pl.DataFrame:
    """Load the core lookup in the legacy column shape used by this pipeline."""
    return pl.read_parquet(build_ons_postcode_lookup(output_path=ONS)).select(
        pl.col("pcd").alias("pcds"),
        pl.col("lad").struct.field("code").alias("lad25cd"),
    )


def parse_date_expr(column: str) -> pl.Expr:
    value = pl.col(column).cast(pl.Utf8).str.strip_chars()
    return pl.coalesce(
        value.str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S", strict=False).dt.date(),
        value.str.strptime(pl.Date, "%Y-%m-%d", strict=False),
        value.str.strptime(pl.Date, "%d/%m/%Y", strict=False),
        value.str.strptime(pl.Date, "%d-%m-%Y", strict=False),
        value.str.strptime(pl.Date, "%Y/%m/%d", strict=False),
        value.str.strptime(pl.Date, "%Y%m%d", strict=False),
    )


def apply_category_mapping(value: str | None) -> str:
    if value is None:
        return "None"
    value = str(value).replace(" ", "_").replace("-", "_").lower()
    value = f"classification_{value}"
    for category, values in CATEGORY_MAPPING.items():
        if value in values:
            return category
    return "None"


def _size_category() -> pl.Expr:
    income = pl.col("latest_income").cast(pl.Float64, strict=False)
    return (
        pl.when(income.is_null())
        .then(pl.lit(None, dtype=pl.String))
        .when(income < _SMALL_INCOME_LIMIT)
        .then(pl.lit("Small"))
        .when(income <= _MEDIUM_INCOME_LIMIT)
        .then(pl.lit("Medium"))
        .otherwise(pl.lit("Large"))
    )


def _company_number_expr(column: str) -> pl.Expr:
    value = pl.col(column).cast(pl.String).str.strip_chars().str.to_uppercase()
    return (
        pl.when(value.is_in(["", "NAN", "NONE", "NULL"]))
        .then(pl.lit(None, dtype=pl.String))
        .when(value.str.contains(r"^\d{1,8}$"))
        .then(value.str.pad_start(8, "0"))
        .otherwise(value)
        .alias(column)
    )


def clean_charity(charity: pl.DataFrame) -> pl.DataFrame:
    charity = charity.rename(lambda col: col.strip())
    # Linked funds are not separate registered charities. Use the main record
    # so a removed linked fund cannot make an active parent appear removed.
    if "linked_charity_number" in charity.columns:
        charity = charity.filter(
            pl.col("linked_charity_number").cast(pl.Int64, strict=False) == 0
        )

    charity = (
        charity.with_columns(
            pl.col("registered_charity_number").cast(pl.Utf8).str.strip_chars(),
            _company_number_expr("charity_company_registration_number"),
            pl.col("latest_income").cast(pl.Float64, strict=False),
            parse_date_expr("date_of_registration").alias("date_of_registration"),
            parse_date_expr("date_of_removal").alias("date_of_removal"),
            (
                pl.col("charity_has_land")
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.to_uppercase()
                == "TRUE"
            ).alias("charity_has_land"),
        )
        .with_columns(
            (
                pl.col("charity_company_registration_number").is_not_null()
                & (
                    ~pl.col("charity_company_registration_number").is_in(
                        ["", "nan", "none"]
                    )
                )
            )
            .cast(pl.Int8)
            .alias("has_company_number"),
            pl.when(pl.col("date_of_removal").is_null())
            .then(pl.lit("active"))
            .otherwise(pl.lit("inactive"))
            .alias("charity_status"),
            pl.when(pl.col("date_of_registration").is_null())
            .then(None)
            .when(pl.col("date_of_registration").dt.month() >= 4)
            .then(pl.col("date_of_registration").dt.year())
            .otherwise(pl.col("date_of_registration").dt.year() - 1)
            .alias("registration_fy"),
            pl.when(pl.col("date_of_removal").is_null())
            .then(None)
            .when(pl.col("date_of_removal").dt.month() >= 4)
            .then(pl.col("date_of_removal").dt.year())
            .otherwise(pl.col("date_of_removal").dt.year() - 1)
            .alias("removal_fy"),
            _size_category().alias("size_category"),
        )
        .sort(
            by=["registered_charity_number", "has_company_number", "date_of_removal"],
            descending=[False, True, True],
        )
        .unique(subset=["registered_charity_number"], keep="first")
    )

    return charity


def clean_charity_classification(charity_classification: pl.DataFrame) -> pl.DataFrame:
    charity_classification = charity_classification.rename(lambda col: col.strip())

    df = (
        charity_classification.with_columns(
            pl.col("registered_charity_number").cast(pl.Utf8).str.strip_chars()
        )
        .with_columns(
            pl.col("classification_description")
            .map_elements(apply_category_mapping, return_dtype=pl.Utf8)
            .alias("classification_description")
        )
        .unique(
            subset=["registered_charity_number", "classification_description"],
            keep="first",
        )
    )

    classification_dummies = (
        df.select("registered_charity_number", "classification_description")
        .filter(pl.col("classification_description").is_not_null())
        .with_columns(pl.lit(1).alias("value"))
        .pivot(
            index="registered_charity_number",
            on="classification_description",
            values="value",
            aggregate_function="max",
        )
    ).fill_null(0)

    # Keep a stable set of indicators, including when a category is absent.
    return classification_dummies.with_columns(
        pl.lit(0, dtype=pl.Int32).alias(category)
        for category in CATEGORY_MAPPING
        if category not in classification_dummies.columns
    )


def clean_company_house(company_house: pl.DataFrame) -> pl.DataFrame:
    company_house = company_house.rename(lambda col: col.strip())
    return company_house.with_columns(
        _company_number_expr("CompanyNumber")
    )


def clean_find_that_charity(find_that_charity: pl.DataFrame) -> pl.DataFrame:
    find_that_charity = find_that_charity.rename(lambda col: col.strip())
    if "source" in find_that_charity.columns:
        find_that_charity = find_that_charity.filter(pl.col("source") == "ccew")
    elif "id" in find_that_charity.columns:
        find_that_charity = find_that_charity.filter(
            pl.col("id").str.starts_with("GB-CHC-")
        )
    rename_map = {}
    if "name" in find_that_charity.columns:
        rename_map["name"] = "charity_name"
    if "charityNumber" in find_that_charity.columns:
        rename_map["charityNumber"] = "registered_charity_number"
    if rename_map:
        find_that_charity = find_that_charity.rename(rename_map)

    return find_that_charity.with_columns(
        pl.col("registered_charity_number").cast(pl.Utf8).str.strip_chars()
    )


def charity_address(df: pl.DataFrame) -> pl.DataFrame:
    # Convert empty string values to nulls
    postcode_cols = ["RegAddress.PostCode", "charity_contact_postcode", "postalCode"]
    df = df.with_columns(
        pl.when(pl.col(col).cast(pl.Utf8).str.strip_chars().str.to_lowercase().is_in(["", "nan", "none", "null"]))
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
        postcode
        .str.to_uppercase()
        .str.replace_all(r"\s+", "")
        .alias("charity_postcode")
    )


def make_postcode_to_local_authority_lookup(ons: pl.DataFrame) -> pl.DataFrame:
    return ons.select(
        pl.col("pcds")
        .cast(pl.Utf8)
        .str.strip_chars()
        .str.to_uppercase()
        .str.replace_all(r"\s+", "")
        .alias("charity_postcode"),
        pl.col("lad25cd").cast(pl.Utf8).str.strip_chars().alias("local_authority_code"),
    ).unique(subset=["charity_postcode"], keep="first")


def merge_charity_data(
    charity: pl.DataFrame,
    charity_class: pl.DataFrame,
    company_house: pl.DataFrame,
    find_that_charity: pl.DataFrame,
    ons: pl.DataFrame,
) -> pl.DataFrame:
    """End-to-end processing and merging of all charity data."""
    charity = clean_charity(charity)
    charity_class = clean_charity_classification(charity_class)
    company_house = clean_company_house(company_house)
    find_that_charity = clean_find_that_charity(find_that_charity)
    la_lookup = make_postcode_to_local_authority_lookup(ons)

    df = (
        charity.join(charity_class, on="registered_charity_number", how="left", validate="1:1")
        .join(
            company_house,
            left_on="charity_company_registration_number",
            right_on="CompanyNumber",
            how="left",
            validate="m:1",
        )
        .join(find_that_charity, on="registered_charity_number", how="left", validate="1:1")
        .with_columns(pl.col(list(CATEGORY_MAPPING)).fill_null(0))
    )

    df = charity_address(df)
    df = df.join(la_lookup, on="charity_postcode", how="left", validate="m:1")

    return df


def load_charity_register(
    charity: pl.DataFrame | None = None,
    charity_class: pl.DataFrame | None = None,
    company_house: pl.DataFrame | None = None,
    find_that_charity: pl.DataFrame | None = None,
    ons: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Load and merge all charity data."""
    if charity is None:
        charity = load_charity()
    if charity_class is None:
        charity_class = load_charity_classification()
    if company_house is None:
        logger.info("Loading Companies House records for charity company numbers")
        company_numbers = charity.rename(lambda col: col.strip()).select(
            _company_number_expr("charity_company_registration_number")
        ).to_series()
        company_house = load_company_house(company_numbers)
    if find_that_charity is None:
        find_that_charity = load_find_that_charity()
    if ons is None:
        ons = load_ons()

    logger.info("Merging charity, classification, company, and postcode data")
    return merge_charity_data(
        charity,
        charity_class,
        company_house,
        find_that_charity,
        ons,
    )


def build_charity_register(
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Save a new run, appending its UTC start time to the configured basename."""
    run_time = datetime.now(timezone.utc)
    started_at = run_time.isoformat()
    inputs = {
        name: _file_record(path) for name, path in {
            "charity_commission": CHARITY,
            "charity_classification": CHARITY_CLASSIFICATION,
            "companies_house": COMPANY_HOUSE,
            "find_that_charity": FIND_THAT_CHARITY,
        }.items()
    }
    ons_mode = (
        "standalone_csv" if ons_datasets.ONS_SOURCE_CSV is not None
        else "cached_parquet" if ONS.is_file()
        else "archive"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    register = load_charity_register()
    inputs["ons_lookup"] = _file_record(ONS)
    if ons_mode == "standalone_csv":
        inputs["ons_source_csv"] = _file_record(ons_datasets.ONS_SOURCE_CSV)
    elif ons_mode == "archive":
        inputs["ons_archive"] = _file_record(
            ons_datasets.DEFAULT_RAW_DIR / ons_datasets.ONS_POSTCODE_LOOKUP_FILENAME
        )
    with TemporaryDirectory(dir=output_path.parent, prefix=".charity-register-") as directory:
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
                "ons": {
                    "mode": ons_mode,
                    "configured_download_url": ons_datasets.ONS_POSTCODE_LOOKUP_URL,
                    "configured_archive_filename": ons_datasets.ONS_POSTCODE_LOOKUP_FILENAME,
                    "note": "Configured endpoint is not verified provenance for an existing cached lookup.",
                },
                "output": {
                    "path": str(saved_path.resolve()),
                    "size_bytes": temporary_path.stat().st_size,
                    "rows": register.height,
                    "columns": register.width,
                },
            }
            temporary_record = Path(directory) / "run.json"
            temporary_record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
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
    base = output_path if output_path is not None else DEFAULT_OUTPUT_PATH
    pattern = re.compile(
        rf"{re.escape(base.stem)}_\d{{8}}_\d{{6}}_\d{{6}}Z{re.escape(base.suffix)}"
    )
    runs = [
        path for path in base.parent.iterdir()
        if path.is_file() and pattern.fullmatch(path.name)
    ] if base.parent.is_dir() else []
    if runs:
        return max(runs, key=lambda path: path.name)
    if base.is_file():
        return base
    raise FileNotFoundError(f"No charity register found in {base.parent}; run the core build first")


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
