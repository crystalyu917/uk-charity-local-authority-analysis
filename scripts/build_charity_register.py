"""Prepare ONS geography and build the charity register."""

import logging
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uk_charity_local_authority_analysis.charity_commission_register import (
    build_charity_register,
)
from uk_charity_local_authority_analysis.charity_commission_register.ons import build_ons_postcode_lookup
from uk_charity_local_authority_analysis.charity_commission_register.utla import latest_utla_lookup

# Edit these inputs and output basename for this run.
DATA_DIR = PROJECT_ROOT / "data" / "charity_commission_register"
# Set this to the folder date when using an older ONS download.
DOWNLOAD_DATE = date.today().strftime("%d%m%Y")
ONS_ARCHIVE_FILEPATH = DATA_DIR / "ons" / DOWNLOAD_DATE / "ONSPD_MAY_2026.zip"
# Set a CSV filepath to rebuild from a standalone postcode source instead.
ONS_SOURCE_CSV_FILEPATH = None
CHARITY_FILEPATH = DATA_DIR / "charity_commission" / "28052025_legacy" / "charity_commission_28052025.csv"
CHARITY_CLASSIFICATION_FILEPATH = DATA_DIR / "charity_commission" / "28052025_legacy" / "charity_classification_28052025.csv"
COMPANY_HOUSE_FILEPATH = DATA_DIR / "company_house" / "28052025_legacy" / "company_house_28052025.csv"
FIND_THAT_CHARITY_FILEPATH = DATA_DIR / "find_that_charity_28052025_legacy" / "find_that_charity_28052025.csv"
ONS_LOOKUP_FILEPATH = DATA_DIR / "ons" / DOWNLOAD_DATE / "ons_postcode_lookup.parquet"
CHARITY_REGISTER_FILEPATH = DATA_DIR / "output" / "charity_register.parquet"
# None selects the newest dated UTLA download; set a CSV path to pin it.
UTLA_LOOKUP_FILEPATH = None
# The builder adds a UTC timestamp and writes a .run.json beside the Parquet.

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    utla_filepath = UTLA_LOOKUP_FILEPATH if UTLA_LOOKUP_FILEPATH is not None else latest_utla_lookup(DATA_DIR / "utla_lookup")
    ons_filepath = build_ons_postcode_lookup(
        output_path=ONS_LOOKUP_FILEPATH,
        source_csv=ONS_SOURCE_CSV_FILEPATH,
        archive_filepath=ONS_ARCHIVE_FILEPATH,
    )
    print(ons_filepath)
    register_filepath = build_charity_register(
        output_path=CHARITY_REGISTER_FILEPATH,
        charity_filepath=CHARITY_FILEPATH,
        classification_filepath=CHARITY_CLASSIFICATION_FILEPATH,
        company_house_filepath=COMPANY_HOUSE_FILEPATH,
        find_that_charity_filepath=FIND_THAT_CHARITY_FILEPATH,
        ons_filepath=ons_filepath,
        utla_filepath=utla_filepath,
    )
    print(register_filepath)
