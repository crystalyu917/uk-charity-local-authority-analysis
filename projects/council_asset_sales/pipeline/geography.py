"""LAD25 code harmonisation and English authority lookup for the panel."""

from typing import Final

import polars as pl

# Retired LAD codes observed in the 2018-19 to 2024-25 receipts source.
# Each predecessor LAD maps wholly to one LAD25 successor.
LAD25_CODE_CROSSWALK: Final[dict[str, str]] = {
    "E06000028": "E06000058",
    "E06000029": "E06000058",
    "E07000004": "E06000060",
    "E07000005": "E06000060",
    "E07000006": "E06000060",
    "E07000007": "E06000060",
    "E07000026": "E06000063",
    "E07000027": "E06000064",
    "E07000028": "E06000063",
    "E07000029": "E06000063",
    "E07000030": "E06000064",
    "E07000031": "E06000064",
    "E07000048": "E06000058",
    "E07000049": "E06000059",
    "E07000050": "E06000059",
    "E07000051": "E06000059",
    "E07000052": "E06000059",
    "E07000053": "E06000059",
    "E07000150": "E06000061",
    "E07000151": "E06000062",
    "E07000152": "E06000061",
    "E07000153": "E06000061",
    "E07000154": "E06000062",
    "E07000155": "E06000062",
    "E07000156": "E06000061",
    "E07000163": "E06000065",
    "E07000164": "E06000065",
    "E07000165": "E06000065",
    "E07000166": "E06000065",
    "E07000167": "E06000065",
    "E07000168": "E06000065",
    "E07000169": "E06000065",
    "E07000187": "E06000066",
    "E07000188": "E06000066",
    "E07000189": "E06000066",
    "E07000190": "E06000066",
    "E07000191": "E06000066",
    "E07000201": "E07000245",
    "E07000204": "E07000245",
    "E07000205": "E07000244",
    "E07000206": "E07000244",
    "E07000246": "E06000066",
    "E08000016": "E08000038",
    "E08000019": "E08000039",
}

_CURRENT_LAD_COLUMNS: Final = (
    "local_authority_code",
    "local_authority",
    "region_code",
    "region_name",
)


def harmonise_lad25_codes(
    frame: pl.LazyFrame,
    column: str = "local_authority_code",
) -> pl.LazyFrame:
    """Replace retired English LAD codes with their LAD25 successors."""
    _require_columns(frame, (column,))
    return frame.with_columns(
        pl.col(column)
        .cast(pl.String)
        .str.strip_chars()
        .replace(LAD25_CODE_CROSSWALK)
        .alias(column)
    )


def prepare_current_english_lads(postcodes: pl.LazyFrame) -> pl.LazyFrame:
    """Return one current English LAD and region record per LAD25 code."""
    _require_columns(postcodes, ("lad", "region"))
    _require_struct_fields(postcodes, "lad", ("code", "name"))
    _require_struct_fields(postcodes, "region", ("code", "name"))

    current_lads = postcodes.select(
        pl.col("lad").struct.field("code").alias("local_authority_code"),
        pl.col("lad").struct.field("name").alias("local_authority"),
        pl.col("region").struct.field("code").alias("region_code"),
        pl.col("region").struct.field("name").alias("region_name"),
    )
    return (
        current_lads.filter(
            pl.col("local_authority_code").str.starts_with("E")
            & pl.col("region_code").str.starts_with("E")
        )
        .unique()
        .select(_CURRENT_LAD_COLUMNS)
        .sort("local_authority_code")
    )


def _require_columns(frame: pl.LazyFrame, required: tuple[str, ...]) -> None:
    columns = set(frame.collect_schema().names())
    missing = sorted(set(required) - columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _require_struct_fields(
    frame: pl.LazyFrame,
    column: str,
    required: tuple[str, ...],
) -> None:
    dtype = frame.collect_schema()[column]
    if not isinstance(dtype, pl.Struct):
        raise TypeError(f"Expected {column} to be a struct column")

    fields = {field.name for field in dtype.fields}
    missing = sorted(set(required) - fields)
    if missing:
        raise ValueError(f"Missing required {column} fields: {missing}")
