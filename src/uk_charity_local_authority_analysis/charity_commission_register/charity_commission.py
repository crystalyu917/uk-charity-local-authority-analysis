"""Charity Commission archive extraction, CSV loading, and preparation."""

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from uk_charity_local_authority_analysis.charity_commission_register.config import CATEGORY_MAPPING, SMALL_INCOME_LIMIT, MEDIUM_INCOME_LIMIT
from uk_charity_local_authority_analysis.charity_commission_register.company_house import _company_number_expr
from uk_charity_local_authority_analysis.charity_commission_register.download_and_extract import extract_single_file_zip
from uk_charity_local_authority_analysis.charity_commission_register.filepath import (
    CHARITY_FILEPATH, CHARITY_CLASSIFICATION_FILEPATH,
    CHARITY_COMMISSION_CHARITY_ARCHIVE_FILEPATH,
    CHARITY_COMMISSION_CLASSIFICATION_ARCHIVE_FILEPATH,
)


@dataclass(frozen=True, slots=True)
class CharityCommissionFiles:
    """Paths to the two archives, or their extracted source files."""

    charity: Path
    classification: Path


def extract_charity_commission(
    dest_dir: Path | None = None,
    *,
    charity_archive_filepath: Path = CHARITY_COMMISSION_CHARITY_ARCHIVE_FILEPATH,
    classification_archive_filepath: Path = CHARITY_COMMISSION_CLASSIFICATION_ARCHIVE_FILEPATH,
    charity_output_filepath: Path | None = None,
    classification_output_filepath: Path | None = None,
) -> CharityCommissionFiles:
    """Safely extract each local archive's sole source file.

    By default, each file lives beneath an archive-named directory beside its ZIP.
    Explicit output filepaths override those destinations and filenames. dest_dir,
    when supplied, selects the directory containing both input archives.
    Extraction preserves source bytes and reuses files with matching sizes.
    These JSON sources are not converted to the legacy register CSV schema.
    """
    archives = CharityCommissionFiles(
        charity=(dest_dir / charity_archive_filepath.name) if dest_dir is not None else charity_archive_filepath,
        classification=(dest_dir / classification_archive_filepath.name) if dest_dir is not None else classification_archive_filepath,
    )
    for path in (archives.charity, archives.classification):
        if not path.is_file():
            raise FileNotFoundError(f"Charity Commission archive not found: {path}. Run its download script first.")
    return CharityCommissionFiles(
        charity=extract_single_file_zip(
            archives.charity, dest_dir=archives.charity.parent,
            output_filepath=charity_output_filepath,
        ),
        classification=extract_single_file_zip(
            archives.classification, dest_dir=archives.classification.parent,
            output_filepath=classification_output_filepath,
        ),
    )


def load_charity(filepath: Path = CHARITY_FILEPATH) -> pl.DataFrame:
    return pl.read_csv(filepath, infer_schema=False)


def load_charity_classification(filepath: Path = CHARITY_CLASSIFICATION_FILEPATH) -> pl.DataFrame:
    return pl.read_csv(filepath, infer_schema=False)


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
        .when(income < SMALL_INCOME_LIMIT)
        .then(pl.lit("Small"))
        .when(income <= MEDIUM_INCOME_LIMIT)
        .then(pl.lit("Medium"))
        .otherwise(pl.lit("Large"))
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


