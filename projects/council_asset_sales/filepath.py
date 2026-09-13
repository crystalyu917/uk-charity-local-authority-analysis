"""Default council analysis filepaths; callers may supply explicit overrides."""

from pathlib import Path
from datetime import date, datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DATA_DIR = PROJECT_ROOT / "projects" / "council_asset_sales" / "datasets"
LA_RECEIPTS_DIR = PROJECT_DATA_DIR / "la_receipts"
LA_RECEIPTS_FILENAME = "la_receipts.csv"
def latest_dated_file(directory: Path, filename: str) -> Path:
    """Select an existing file by folder date, ignoring names such as *_legacy.

    Fall back to today's expected path if no dated snapshot contains the file.
    """
    candidates = []
    for path in directory.glob(f"*/{filename}"):
        try:
            snapshot_date = datetime.strptime(path.parent.name, "%d%m%Y")
        except ValueError:
            continue
        if path.is_file():
            candidates.append((snapshot_date, path))
    return max(candidates, key=lambda item: item[0])[1] if candidates else directory / date.today().strftime("%d%m%Y") / filename


LA_RECEIPTS_FILEPATH = latest_dated_file(LA_RECEIPTS_DIR, LA_RECEIPTS_FILENAME)
# None selects the latest register in this project's charity_register_inputs folder.
# Set an explicit local file below to pin a particular snapshot.
CHARITY_REGISTER_FILEPATH: Path | None = None
CHARITY_REGISTER_INPUTS_DIR = PROJECT_DATA_DIR / "charity_register_inputs"
CHARITY_REGISTER_BASE_FILEPATH = CHARITY_REGISTER_INPUTS_DIR / "charity_register.parquet"
CHARITY_LA_RECEIPTS_PANEL_FILEPATH = PROJECT_DATA_DIR / "output" / "charity_la_receipts_panel.parquet"
ONS_LOOKUP_FILEPATH = latest_dated_file(
    PROJECT_ROOT / "data" / "charity_commission_register" / "ons", "ons_postcode_lookup.parquet",
)
