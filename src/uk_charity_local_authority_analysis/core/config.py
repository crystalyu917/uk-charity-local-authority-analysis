"""Edit data locations and download settings here, then rerun the command.

Directories can be repo-relative (PROJECT_ROOT / "...") or absolute
(Path("D:/datasets/...")); filenames must match the selected source files.
Changing locations does not adapt a different source's CSV schema.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "core"
DEFAULT_STAGING_DIR = DEFAULT_DATA_DIR / "staging"
OUTPUT_DIR = DEFAULT_DATA_DIR / "output"

# Change "legacy_raw" to "raw", or supply an absolute directory.
CHARITY_COMMISSION_DIR = DEFAULT_DATA_DIR / "charity_commission" / "legacy_raw"
COMPANY_HOUSE_DIR = DEFAULT_DATA_DIR / "company_house" / "legacy_raw"
FIND_THAT_CHARITY_DIR = DEFAULT_DATA_DIR / "find_that_charity" / "legacy_raw"

CHARITY = CHARITY_COMMISSION_DIR / "charity_commission_28052025.csv"
CHARITY_CLASSIFICATION = CHARITY_COMMISSION_DIR / "charity_classification_28052025.csv"
COMPANY_HOUSE = COMPANY_HOUSE_DIR / "company_house_28052025.csv"
FIND_THAT_CHARITY = FIND_THAT_CHARITY_DIR / "find_that_charity_28052025.csv"
# Base filename: each build appends _YYYYMMDD_HHMMSS_microsecondsZ (UTC).
CHARITY_OUTPUT_PATH = OUTPUT_DIR / "charity_register.parquet"

# ONS is currently the only source with an implemented downloader.
ONS_RAW_DIR = DEFAULT_DATA_DIR / "ons" / "raw"
ONS_POSTCODE_LOOKUP_ITEM_ID = "6fff67d204fd4f339591ed667a6e3642"
ONS_POSTCODE_LOOKUP_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ONS_POSTCODE_LOOKUP_ITEM_ID}/data"
)
ONS_POSTCODE_LOOKUP_FILENAME = "ONSPD_MAY_2026.zip"
ONS_OUTPUT_PATH = ONS_RAW_DIR / "ons_postcode_lookup.parquet"

# None downloads/extracts the official archive and joins geography names.
# Set a Path to use a standalone CSV instead (geography names will be null).
# Example: ONS_SOURCE_CSV = ONS_RAW_DIR / "my_postcodes.csv"
ONS_SOURCE_CSV: Path | None = None

# Downloads and ONS Parquet outputs are cached. When switching ONS releases,
# change the ZIP filename and output path, or remove the old cached files.
