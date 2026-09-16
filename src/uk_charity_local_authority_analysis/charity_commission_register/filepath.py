"""Legacy register inputs and dated download/preparation defaults.

Library functions accept explicit filepath overrides. Scripts declare their own
paths; changing these defaults does not override a script's explicit arguments.
"""

from datetime import date
from pathlib import Path

from uk_charity_local_authority_analysis.charity_commission_register.config import (
    UTLA_ARCHIVE_FILENAME, UTLA_CSV_FILENAME,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "charity_commission_register"
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
    CHARITY_COMMISSION_RAW_DIR / "publicextract.charity.zip"
)
CHARITY_COMMISSION_CLASSIFICATION_ARCHIVE_FILEPATH = (
    CHARITY_COMMISSION_RAW_DIR / "publicextract.charity_classification.zip"
)
CHARITY_COMMISSION_CHARITY_JSON_FILEPATH = (
    CHARITY_COMMISSION_RAW_DIR / "publicextract.charity" / "publicextract.charity.json"
)
CHARITY_COMMISSION_CLASSIFICATION_JSON_FILEPATH = (
    CHARITY_COMMISSION_RAW_DIR
    / "publicextract.charity_classification"
    / "publicextract.charity_classification.json"
)
ONS_RAW_DIR = DEFAULT_DATA_DIR / "ons" / DOWNLOAD_DATE
ONS_ARCHIVE_FILEPATH = ONS_RAW_DIR / "ONSPD_MAY_2026.zip"
ONS_LOOKUP_FILEPATH = ONS_RAW_DIR / "ons_postcode_lookup.parquet"
ONS_SOURCE_CSV_FILEPATH: Path | None = None
UTLA_LOOKUP_DIR = DEFAULT_DATA_DIR / "utla_lookup"
UTLA_ARCHIVE_FILEPATH = UTLA_LOOKUP_DIR / DOWNLOAD_DATE / UTLA_ARCHIVE_FILENAME
UTLA_LOOKUP_FILEPATH = UTLA_ARCHIVE_FILEPATH.with_suffix("") / UTLA_CSV_FILENAME
