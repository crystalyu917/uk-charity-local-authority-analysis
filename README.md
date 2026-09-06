# UK charity local authority analysis

Build a charity register from Charity Commission, Companies House, Find That
Charity, and ONS postcode data, then aggregate removals by local authority.

## Configure inputs

All data paths and download settings live in
[`core/config.py`](src/uk_charity_local_authority_analysis/core/config.py).
Edit this file, save it, and rerun the command. Restart Python if using a notebook.

| Source or output | Settings |
| --- | --- |
| Charity Commission | `CHARITY_COMMISSION_DIR`, `CHARITY`, `CHARITY_CLASSIFICATION` |
| Companies House | `COMPANY_HOUSE_DIR`, `COMPANY_HOUSE` |
| Find That Charity | `FIND_THAT_CHARITY_DIR`, `FIND_THAT_CHARITY` |
| ONS download | `ONS_POSTCODE_LOOKUP_ITEM_ID`, `ONS_POSTCODE_LOOKUP_URL`, `ONS_POSTCODE_LOOKUP_FILENAME` |
| ONS local files | `ONS_RAW_DIR`, `ONS_SOURCE_CSV`, `ONS_OUTPUT_PATH` |
| Register output basename | `CHARITY_OUTPUT_PATH` |

The defaults select May 2025 CSVs in each source's `legacy_raw` folder and the
May 2026 ONS release. Supply the CSVs locally; only ONS has a downloader.
To choose different data, change the directory and filenames together:

```python
CHARITY_COMMISSION_DIR = DEFAULT_DATA_DIR / "charity_commission" / "raw"
CHARITY = CHARITY_COMMISSION_DIR / "charity_commission_latest.csv"
CHARITY_CLASSIFICATION = CHARITY_COMMISSION_DIR / "charity_classification_latest.csv"

# Absolute directories also work.
COMPANY_HOUSE_DIR = Path("D:/datasets/companies")
COMPANY_HOUSE = COMPANY_HOUSE_DIR / "companies.csv"
```

Anchor repo-relative paths to `PROJECT_ROOT` or `DEFAULT_DATA_DIR`. Replacement
CSVs must retain the columns expected by the pipeline.

For ONS, change the item ID or supply a direct compatible ZIP URL. Keep the ZIP
filename aligned with the release. Downloads and ONS Parquet files are cached:
use new filenames/paths or remove the old cached files when switching releases.
Extracted CSVs are reused when their sizes match the archive metadata.

Leave `ONS_SOURCE_CSV = None` to use the archive and geography name lookups, or
set it to a local CSV path. A configured CSV rebuilds the ONS Parquet on each
build and supplies geography codes with null names; it does not affect the
`download` and `extract` commands.

## Run

Install `uv`, then run these PowerShell commands from the repository root.
`uv run` sets up Python 3.14 and the project dependencies as needed.

Build the complete charity register (builds the ONS lookup if needed):

```powershell
uv run python -m uk_charity_local_authority_analysis.core
```

To run ONS preparation separately:

```powershell
uv run python -m uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup download
```

| Action | Result under the default `data\core\ons\raw` directory |
| --- | --- |
| `download` | Download the ONS ZIP |
| `extract` | Download and extract the postcode, LAD, and region CSVs |
| `build` (default if omitted) | Create `ons_postcode_lookup.parquet` with postcode, LAD, and region codes/names |

## Outputs and run records

Each successful register build saves two files beside the configured
`CHARITY_OUTPUT_PATH`. By default:

```text
data/core/output/
  charity_register_20260906_143025_123456Z.parquet
  charity_register_20260906_143025_123456Z.run.json
```

The suffix is the run's UTC start time, including microseconds (`Z` means UTC).
Previous runs are preserved, including when timestamps collide. The command
prints the Parquet path and logs the JSON path.

The JSON records:

- UTC start and completion times.
- Input dataset paths, sizes, and modification timestamps.
- ONS source mode (cached lookup, local CSV, or archive) and configured endpoint.
- Saved Parquet path, size, and row/column counts.

Records describe successful builds only; older outputs are not backfilled.
They contain file metadata, not copies or hashes of the inputs. A configured
ONS endpoint does not establish the origin of an existing cached lookup.
If record publication fails, the new Parquet is removed and the build reports
an error.

## Analyse removals

```python
from pathlib import Path
from uk_charity_local_authority_analysis.core.charity import scan_charity_removals

# Latest timestamped run; falls back to the old unsuffixed file if necessary.
removals = scan_charity_removals().collect()

# Or select a specific run.
removals = scan_charity_removals(
    Path("data/core/output/charity_register_20260906_143025_123456Z.parquet")
).collect()
```

Results group removals by local authority, financial year, and size. Rows without
a local authority or removal year are excluded.

The pipeline uses these conventions:

- England and Wales main charity records (`linked_charity_number = 0`), with
  Find That Charity restricted to `ccew`. Linked-fund classifications contribute
  to the parent charity; absent classification flags are zero.
- Company numbers remain strings, with numeric identifiers padded to eight
  characters. Joins validate lookup uniqueness to avoid multiplying rows.
- Postcode priority: Companies House, Charity Commission, then Find That Charity.
  Unmatched postcodes retain a null local authority code.
- Financial years start in April. Income bands: Small below 25,000; Medium from
  25,000 through 1,000,000; Large above 1,000,000. Missing income is unclassified.
- Geography comes from the configured ONS release, rather than being reconstructed
  for each historical removal date.

## Tests

Tests live in `tests/` subfolders of their relevant modules under `src/`.

```powershell
uv run python -m unittest discover -s src -v
```
