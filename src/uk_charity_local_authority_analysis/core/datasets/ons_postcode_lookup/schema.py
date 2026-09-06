"""Polars schema for the ONS postcode lookup."""

from typing import Final

import polars as pl

_AREA_SCHEMA: Final = pl.Struct(
    {
        "code": pl.String,
        "name": pl.String,
    }
)

ONS_POSTCODE_LOOKUP_SCHEMA: Final[pl.Schema] = pl.Schema(
    {
        "pcd": pl.String,
        "lad": _AREA_SCHEMA,
        "region": _AREA_SCHEMA,
    }
)
