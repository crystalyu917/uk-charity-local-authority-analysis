"""Polars schema construction for local authority capital receipts data."""

from typing import TYPE_CHECKING, Final

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Sequence

FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN: Final = "EandR1_alltot_rectot"

LA_CAPITAL_RECEIPTS_IDENTIFIER_SCHEMA: Final[pl.Schema] = pl.Schema(
    {
        "PeriodCode": pl.Int32,
        "LA_LGF_Code": pl.String,
        "ONS_Code": pl.String,
        "LA_Name": pl.String,
        "LA_Class": pl.String,
        "LA_Subclass": pl.String,
        "Status": pl.String,
    }
)


def build_la_capital_receipts_schema(column_names: Sequence[str]) -> pl.Schema:
    """Build the full schema from the CSV header."""
    identifier_names = LA_CAPITAL_RECEIPTS_IDENTIFIER_SCHEMA.names()
    actual_identifier_names = list(column_names[: len(identifier_names)])
    if actual_identifier_names != identifier_names:
        raise ValueError(
            f"Unexpected local authority identifier columns: {actual_identifier_names}"
        )

    if len(set(column_names)) != len(column_names):
        raise ValueError("Duplicate columns found in local authority capital data")

    if FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN not in column_names:
        raise ValueError(
            "Fixed-asset disposal receipts column is missing: "
            f"{FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN}"
        )

    return pl.Schema(
        {
            column_name: LA_CAPITAL_RECEIPTS_IDENTIFIER_SCHEMA.get(
                column_name,
                pl.Int64,
            )
            for column_name in column_names
        }
    )
