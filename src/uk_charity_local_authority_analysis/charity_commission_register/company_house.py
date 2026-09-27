"""Companies House CSV loading and company-number normalisation."""

import csv
import logging
import re
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
    try:
        return companies.collect(engine="streaming")
    except pl.exceptions.ComputeError as error:
        if company_numbers is None or "found more fields than defined" not in str(error):
            raise
        logging.getLogger(__name__).warning(
            "Companies House CSV has inconsistent field counts; retrying with "
            "row-by-row parsing and validating required company records"
        )
        return _load_required_companies(filepath, company_numbers)


def _load_required_companies(filepath: Path, company_numbers: pl.Series) -> pl.DataFrame:
    """Exclude unrelated records before validating widths; never truncate fields."""
    wanted = set(company_numbers.drop_nulls().to_list())
    rows = []
    with filepath.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        columns = [column.strip() for column in next(reader)]
        number_index = columns.index("CompanyNumber")
        for row in reader:
            if not row:
                continue
            if len(row) <= number_index:
                raise ValueError(f"Missing company number at {filepath}:{reader.line_num}")
            number = row[number_index].strip().upper()
            if re.fullmatch(r"\d{1,8}", number):
                number = number.zfill(8)
            if number not in wanted:
                continue
            if len(row) != len(columns):
                raise ValueError(
                    f"Invalid Companies House record for {number} at "
                    f"{filepath}:{reader.line_num}: expected {len(columns)} "
                    f"fields, found {len(row)}"
                )
            row[number_index] = number
            rows.append([value if value else None for value in row])
    return pl.DataFrame(rows, schema={column: pl.String for column in columns}, orient="row")


def clean_company_house(company_house: pl.DataFrame) -> pl.DataFrame:
    company_house = company_house.rename(lambda col: col.strip())
    return company_house.with_columns(
        _company_number_expr("CompanyNumber")
    )


