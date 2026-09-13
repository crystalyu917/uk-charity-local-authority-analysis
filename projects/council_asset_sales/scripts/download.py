"""Download fresh LA receipts into this project's dated data folder."""

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uk_charity_local_authority_analysis.charity_commission_register.download_and_extract import download_file

from projects.council_asset_sales.config import LA_RECEIPTS_URL
from projects.council_asset_sales.filepath import (
    LA_RECEIPTS_DIR,
    LA_RECEIPTS_FILENAME,
)

if __name__ == "__main__":
    print(download_file(
        LA_RECEIPTS_URL,
        LA_RECEIPTS_DIR / date.today().strftime("%d%m%Y"),
        filename=LA_RECEIPTS_FILENAME,
        refresh=True,
    ))
