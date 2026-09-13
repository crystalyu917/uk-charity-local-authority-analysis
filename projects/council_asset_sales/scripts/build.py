"""Build the council panel from existing receipts, charity register, and ONS data."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from projects.council_asset_sales.pipeline import write_charity_la_receipts_panel


if __name__ == "__main__":
    print(write_charity_la_receipts_panel())
