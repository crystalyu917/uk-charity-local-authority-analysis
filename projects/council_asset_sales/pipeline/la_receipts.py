"""Load local-authority receipts CSVs for the council analysis."""

from pathlib import Path
import polars as pl
from projects.council_asset_sales import filepath

FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN = "EandR1_alltot_rectot"
REQUIRED_COLUMNS = (
    "PeriodCode", "LA_LGF_Code", "ONS_Code", "LA_Name", "LA_Class",
    "LA_Subclass", "Status", FIXED_ASSET_DISPOSAL_RECEIPTS_COLUMN,
)


def scan_la_receipts(dest_dir: Path | None = None, *, input_filepath: Path | None = None) -> pl.LazyFrame:
    path = input_filepath if input_filepath is not None else filepath.LA_RECEIPTS_FILEPATH
    if dest_dir is not None and input_filepath is None:
        path = dest_dir / filepath.LA_RECEIPTS_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"Receipts CSV not found: {path}. Run projects/council_asset_sales/scripts/download.py first.")
    frame = pl.scan_csv(path, infer_schema=False, null_values=["..", "...", "-", "n/a"])
    missing = set(REQUIRED_COLUMNS).difference(frame.collect_schema().names())
    if missing:
        raise ValueError(f"Missing LA receipts columns: {', '.join(sorted(missing))}")
    return frame


def load_la_receipts(dest_dir: Path | None = None, *, input_filepath: Path | None = None) -> pl.DataFrame:
    return scan_la_receipts(dest_dir, input_filepath=input_filepath).collect(engine="streaming")
