"""Download and extract the November 2023 postcode-to-UTLA lookup."""

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uk_charity_local_authority_analysis.charity_commission_register.download_and_extract import download_file, extract_zip

SOURCE_URL = "https://www.arcgis.com/sharing/rest/content/items/bc8f6d1f6ee64111b6a59b22c6605f3b/data"
ARCHIVE_FILENAME = "PCD_OA21_LSOA21_MSOA21_LTLA22_UTLA22_CAUTH22_NOV23_UK_LU_V2.zip"
DOWNLOAD_DIR = PROJECT_ROOT / "projects" / "council_asset_sales" / "datasets" / "utla_lookup" / date.today().strftime("%d%m%Y")


if __name__ == "__main__":
    archive = download_file(SOURCE_URL, DOWNLOAD_DIR, filename=ARCHIVE_FILENAME, refresh=True)
    print(archive)
    for path in extract_zip(archive, refresh=True):
        print(path)
