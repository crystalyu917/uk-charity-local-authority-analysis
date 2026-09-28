"""Legacy register inputs and dated download/preparation defaults.

Library functions accept explicit filepath overrides. Scripts declare their own
paths; changing these defaults does not override a script's explicit arguments.
"""

from datetime import date
from pathlib import Path

from uk_charity_local_authority_analysis.charity_commission_register.config import (
    DEFAULT_DATA_DIR,
    PROJECT_ROOT,
    CHARITY_COMMISSION_CHARITY_FILENAME,
    CHARITY_COMMISSION_CLASSIFICATION_FILENAME,
    ONSPD_POSTCODE_LOOKUP_FILENAME,
    UTLA_ARCHIVE_FILENAME,
    UTLA_CSV_FILENAME,
)

DEFAULT_STAGING_DIR = DEFAULT_DATA_DIR / "staging"
OUTPUT_DIR = DEFAULT_DATA_DIR / "output"
# Local date, evaluated on import. Set a DDMMYYYY string for an older snapshot.
DOWNLOAD_DATE = date.today().strftime("%d%m%Y")
CHARITY_COMMISSION_DIR = DEFAULT_DATA_DIR / "charity_commission" / "28052025_legacy"
COMPANY_HOUSE_DIR = DEFAULT_DATA_DIR / "company_house" / "28052025_legacy"
FIND_THAT_CHARITY_DIR = DEFAULT_DATA_DIR / "find_that_charity_28052025_legacy"
CHARITY_FILEPATH = CHARITY_COMMISSION_DIR / "charity_commission_28052025.csv"
CHARITY_CLASSIFICATION_FILEPATH = (
    CHARITY_COMMISSION_DIR / "charity_classification_28052025.csv"
)
COMPANY_HOUSE_FILEPATH = COMPANY_HOUSE_DIR / "company_house_28052025.csv"
FIND_THAT_CHARITY_FILEPATH = FIND_THAT_CHARITY_DIR / "find_that_charity_28052025.csv"
# Builds append a UTC timestamp to this output basename.
CHARITY_REGISTER_FILEPATH = OUTPUT_DIR / "charity_register.parquet"
CHARITY_COMMISSION_RAW_DIR = DEFAULT_DATA_DIR / "charity_commission" / DOWNLOAD_DATE
CHARITY_COMMISSION_CHARITY_ARCHIVE_FILEPATH = (
    CHARITY_COMMISSION_RAW_DIR / CHARITY_COMMISSION_CHARITY_FILENAME
)
CHARITY_COMMISSION_CLASSIFICATION_ARCHIVE_FILEPATH = (
    CHARITY_COMMISSION_RAW_DIR / CHARITY_COMMISSION_CLASSIFICATION_FILENAME
)
CHARITY_COMMISSION_CHARITY_JSON_FILEPATH = (
    CHARITY_COMMISSION_RAW_DIR / "publicextract.charity" / "publicextract.charity.json"
)
CHARITY_COMMISSION_CLASSIFICATION_JSON_FILEPATH = (
    CHARITY_COMMISSION_RAW_DIR
    / "publicextract.charity_classification"
    / "publicextract.charity_classification.json"
)
ONSPD_RAW_DIR = DEFAULT_DATA_DIR / "onspd" / DOWNLOAD_DATE
ONSPD_ARCHIVE_FILEPATH = ONSPD_RAW_DIR / ONSPD_POSTCODE_LOOKUP_FILENAME
ONSPD_LOOKUP_FILEPATH = ONSPD_RAW_DIR / "onspd_geography_lookup.parquet"
ONSPD_SOURCE_CSV_FILEPATH: Path | None = None
UTLA_LOOKUP_DIR = DEFAULT_DATA_DIR / "utla_lookup"
UTLA_ARCHIVE_FILEPATH = UTLA_LOOKUP_DIR / DOWNLOAD_DATE / UTLA_ARCHIVE_FILENAME
UTLA_LOOKUP_FILEPATH = UTLA_ARCHIVE_FILEPATH.with_suffix("") / UTLA_CSV_FILENAME
