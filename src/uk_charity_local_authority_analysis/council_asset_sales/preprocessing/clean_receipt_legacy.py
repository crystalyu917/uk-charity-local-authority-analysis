"""Compatibility helpers for older in-memory receipt tables.

The supported file-based pipeline is in preprocessing.panel.
"""

import polars as pl

from uk_charity_local_authority_analysis.council_asset_sales import config

CAPITAL_RECEIPTS_COL = "EandR1_alltot_rectot"


unified_map = {
    "buckinghamshire": [
        "aylesbury vale",
        "chiltern",
        "south bucks",
        "wycombe",
        "south buckinghamshire",
    ],
    "dorset": [
        "weymouth and portland",
        "west dorset",
        "north dorset",
        "east dorset",
        "purbeck",
        "christchurch",
    ],
    "somerset": [
        "taunton deane",
        "west somerset",
        "mendip",
        "sedgemoor",
        "south somerset",
        "somerset council",
        "somerset west and taunton",
    ],
    "cumberland": ["allerdale", "carlisle", "copeland", "cumberland council"],
    "westmorland and furness": [
        "barrow in furness",
        "barrow-in-furness",
        "eden",
        "south lakeland",
    ],
    "north yorkshire": [
        "craven",
        "hambleton",
        "harrogate",
        "richmondshire",
        "ryedale",
        "scarborough",
        "selby",
        "north yorkshire council",
    ],
    "bournemouth christchurch and poole": ["bournemouth", "christchurch", "poole"],
    "west suffolk": ["forest heath", "st edmundsbury"],
    "east suffolk": ["suffolk coastal", "waveney"],
    "bath and north east somerset": ["bath and ne somerset"],
    "southend-on-sea": ["southend on sea"],
    "leicester": ["leicester city"],
    "medway": ["medway towns"],
    "derby": ["derby city"],
    "folkestone and hythe": ["shepway"],
    "county durham": ["durham"],
    "king's lynn and west norfolk": ["kings lynn and west norfolk"],
    "north northamptonshire": [
        "wellingborough",
        "east northamptonshire",
        "kettering",
        "corby",
    ],
    "west northamptonshire": ["northampton", "south northamptonshire", "daventry"],
}


flat_lookup = {
    old.lower(): new.lower()
    for new, old_names in unified_map.items()
    for old in old_names
}


non_england_keywords = [
    "aberdeen",
    "aberdeenshire",
    "angus",
    "antrim",
    "ards",
    "argyll",
    "armagh",
    "belfast",
    "blaenau",
    "bridgend",
    "caerphilly",
    "cardiff",
    "carmarthenshire",
    "causeway",
    "ceredigion",
    "conwy",
    "denbighshire",
    "derry",
    "dumfries",
    "dundee",
    "east ayrshire",
    "east dunbartonshire",
    "east lothian",
    "east renfrewshire",
    "falkirk",
    "fermanagh",
    "fife",
    "flintshire",
    "glasgow",
    "gwynedd",
    "highland",
    "inverclyde",
    "isle of man",
    "isle of anglesey",
    "lisburn",
    "merthyr",
    "mid and east antrim",
    "mid ulster",
    "midlothian",
    "monmouthshire",
    "moray",
    "na h eileanan siar",
    "neath",
    "newport",
    "newry",
    "north ayrshire",
    "north lanarkshire",
    "orkney",
    "pembrokeshire",
    "perth and kinross",
    "powys",
    "renfrewshire",
    "rhondda",
    "scottish borders",
    "shetland",
    "south ayrshire",
    "south lanarkshire",
    "stirling",
    "swansea",
    "torfaen",
    "vale of glamorgan",
    "west dunbartonshire",
    "west lothian",
    "wrexham",
    "city of edinburgh",
    "channel islands",
]


def clean_local_authority_expr(column: str) -> pl.Expr:
    return (
        pl.col(column)
        .cast(pl.Utf8)
        .str.to_lowercase()
        .str.replace_all("&", "and")
        .str.replace_all("-", " ")
        .str.replace_all(",", "")
        .str.replace_all(".", "", literal=True)
        .str.replace_all(" city of", "")
        .str.replace_all(" county of", "")
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
        .replace(flat_lookup)
    )


def clean_capital_receipts(capital_receipts: pl.DataFrame) -> pl.DataFrame:
    if CAPITAL_RECEIPTS_COL not in capital_receipts.columns:
        raise ValueError(
            f"Missing expected capital receipts column: {CAPITAL_RECEIPTS_COL}"
        )

    return (
        capital_receipts.select(
            pl.col("PeriodCode").cast(pl.Int64).alias("period_code"),
            pl.col("ONS_Code").cast(pl.Utf8).alias("local_authority_code"),
            pl.col("LA_Name").cast(pl.Utf8).alias("local_authority"),
            pl.col("Status").cast(pl.Utf8).str.to_lowercase().alias("status"),
            pl.col(CAPITAL_RECEIPTS_COL)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.replace_all(",", "")
            .str.replace_all("[z]", "", literal=True)
            .str.replace_all("[x]", "", literal=True)
            .str.replace_all("[c]", "", literal=True)
            .str.replace_all("..", "", literal=True)
            .cast(pl.Float64, strict=False)
            .alias("capital_receipts_thousand"),
        )
        .filter(pl.col("status") == "submitted")
        .with_columns(
            clean_local_authority_expr("local_authority").alias("local_authority"),
            ((pl.col("period_code") // 100) - 1).alias("financial_year"),
            (pl.col("capital_receipts_thousand") / 1000).alias("value"),
        )
        .select(
            "financial_year",
            "local_authority_code",
            "local_authority",
            "value",
        )
        .group_by(
            "financial_year",
            "local_authority_code",
            "local_authority",
        )
        .agg(pl.col("value").sum())
    )


def clean_charity_dataset(charity_df: pl.DataFrame) -> pl.DataFrame:
    return charity_df.with_columns(
        pl.col("local_authority_code").cast(pl.Utf8).str.strip_chars(),
        pl.col("local_authority").cast(pl.Utf8),
        pl.col("removal_fy").cast(pl.Int64, strict=False),
        pl.col("size_category").cast(pl.Utf8),
    )


def create_complete_panel(
    capital_receipts: pl.DataFrame,
    charity_df: pl.DataFrame,
) -> pl.DataFrame:
    receipts = clean_capital_receipts(capital_receipts)
    charities = clean_charity_dataset(charity_df)

    print("Receipts:", receipts.shape)
    print(
        receipts.select(
            pl.col("financial_year").min().alias("min_year"),
            pl.col("financial_year").max().alias("max_year"),
        )
    )

    print("Charities:", charities.shape)
    print(charities.columns)

    removals = (
        charities.filter(
            pl.col("removal_fy").is_not_null()
            & pl.col("size_category").is_not_null()
            & pl.col("local_authority_code").is_not_null()
        )
        .group_by(
            "local_authority_code",
            "removal_fy",
            "size_category",
        )
        .len()
        .rename(
            {
                "removal_fy": "financial_year",
                "len": "removals",
            }
        )
    )

    print("Removals:", removals.shape)

    sizes = pl.DataFrame({"size_category": config.COUNCIL_SIZE_CATEGORIES})

    print("Sizes:", sizes)

    panel = (
        receipts.join(sizes, how="cross")
        .join(
            removals,
            on=[
                "financial_year",
                "local_authority_code",
                "size_category",
            ],
            how="left",
        )
        .with_columns(pl.col("removals").fill_null(0).cast(pl.Int64))
        .filter(pl.col("financial_year").is_between(
            config.COUNCIL_START_YEAR, config.COUNCIL_END_YEAR
        ))
        .sort(
            [
                "local_authority",
                "size_category",
                "financial_year",
            ]
        )
        .with_columns(
            pl.col("value")
            .shift(1)
            .over(["local_authority_code", "size_category"])
            .alias("value_lag1"),
            pl.col("value")
            .shift(2)
            .over(["local_authority_code", "size_category"])
            .alias("value_lag2"),
            pl.col("value")
            .shift(3)
            .over(["local_authority_code", "size_category"])
            .alias("value_lag3"),
        )
    )

    return panel
