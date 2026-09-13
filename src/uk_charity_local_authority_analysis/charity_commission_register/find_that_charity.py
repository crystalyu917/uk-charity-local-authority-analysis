"""Find That Charity CSV loading and preparation."""

from pathlib import Path

import polars as pl

from uk_charity_local_authority_analysis.charity_commission_register.filepath import FIND_THAT_CHARITY_FILEPATH


def load_find_that_charity(filepath: Path = FIND_THAT_CHARITY_FILEPATH) -> pl.DataFrame:
    return pl.read_csv(
        filepath,
        infer_schema=False,
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


