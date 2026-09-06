"""All council asset sales input/output paths, endpoints, and panel settings.

Edit this file and restart Python before rebuilding. CSV downloads are cached;
change the receipt path when changing releases. The legacy workbook is not used.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Council asset sales: inputs stay under this analysis directory; no legacy fallback.
COUNCIL_DATA_DIR = PROJECT_ROOT / "data" / "council_asset_sales"
COUNCIL_RAW_DIR = COUNCIL_DATA_DIR / "raw"
COUNCIL_RECEIPTS_PATH = COUNCIL_RAW_DIR / "la_capital_receipts.csv"
COUNCIL_RECEIPTS_URL = "https://assets.publishing.service.gov.uk/media/69c2a55b13f1436476e4436c/Capital_time_series_data_wide_24_03_26.csv"
# None selects the latest timestamped charity register in COUNCIL_RAW_DIR.
# Set an explicit Path here to pin a particular local run.
COUNCIL_CHARITY_PATH: Path | None = None
COUNCIL_PANEL_OUTPUT_PATH = COUNCIL_DATA_DIR / "output" / "charity_receipts_panel.parquet"
COUNCIL_START_YEAR = 2018
COUNCIL_END_YEAR = 2023

# Reuse the prepared geography file, with its location configured only here.
# No council settings are read from core/config.py.
COUNCIL_POSTCODE_LOOKUP_PATH = (
    PROJECT_ROOT / "data" / "core" / "ons" / "raw" / "ons_postcode_lookup.parquet"
)
COUNCIL_RECEIPTS_PUBLICATION_URL = "https://www.gov.uk/government/statistics/local-authority-capital-expenditure-and-receipts-in-england-final-outturn-time-series"
COUNCIL_SIZE_CATEGORIES = ("Small", "Medium", "Large")
COUNCIL_LAG_PERIODS = (1, 2, 3)
