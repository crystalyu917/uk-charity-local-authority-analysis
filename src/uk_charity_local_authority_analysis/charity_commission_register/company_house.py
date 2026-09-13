"""Companies House CSV loading and company-number normalisation."""

from pathlib import Path

import polars as pl

from uk_charity_local_authority_analysis.charity_commission_register.filepath import COMPANY_HOUSE_FILEPATH


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


def load_company_house(company_numbers: pl.Series | None = None, *, filepath: Path = COMPANY_HOUSE_FILEPATH) -> pl.DataFrame:
    """Read company fields as strings, optionally retaining only needed companies."""
    companies = pl.scan_csv(
        filepath, infer_schema=False,
        with_column_names=lambda columns: [column.strip() for column in columns],
    ).with_columns(_company_number_expr("CompanyNumber"))
    if company_numbers is not None:
        companies = companies.filter(
            pl.col("CompanyNumber").is_in(company_numbers.drop_nulls().implode())
        )
    return companies.collect(engine="streaming")


def clean_company_house(company_house: pl.DataFrame) -> pl.DataFrame:
    company_house = company_house.rename(lambda col: col.strip())
    return company_house.with_columns(
        _company_number_expr("CompanyNumber")
    )


