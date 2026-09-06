# Council asset sales

Build an English local-authority, financial-year, and charity-size panel linking
fixed-asset disposal receipts to charity removals. Code, tests, and the analysis
configuration live in this folder. Default receipts, charity inputs, and panel
outputs live in [`data/council_asset_sales/`](../../../data/council_asset_sales/).

Complete the repository [setup guide](../../../README.md) first. Run all commands
below from the repository root.

## Configure inputs and outputs

Edit only [`config.py`](config.py) for this analysis, then rerun the command.
Restart Python if using a notebook. Council settings are independent of
`core/config.py`; changing the core configuration does not change these paths.

| Setting | Purpose and default |
| --- | --- |
| `COUNCIL_DATA_DIR` | `data/council_asset_sales/` |
| `COUNCIL_RAW_DIR` | `raw/` beneath the analysis data directory |
| `COUNCIL_RECEIPTS_PATH` | `raw/la_capital_receipts.csv` |
| `COUNCIL_RECEIPTS_URL` | Direct CSV download endpoint |
| `COUNCIL_RECEIPTS_PUBLICATION_URL` | Source publication reference |
| `COUNCIL_CHARITY_PATH` | `None`: select the latest local timestamped register |
| `COUNCIL_POSTCODE_LOOKUP_PATH` | Existing `data/core/ons/raw/ons_postcode_lookup.parquet` |
| `COUNCIL_PANEL_OUTPUT_PATH` | `output/charity_receipts_panel.parquet` |
| `COUNCIL_START_YEAR`, `COUNCIL_END_YEAR` | 2018 through 2023 inclusive |
| `COUNCIL_SIZE_CATEGORIES` | Small, Medium, Large |
| `COUNCIL_LAG_PERIODS` | 1, 2, and 3 financial years |

Paths may be absolute or anchored to `PROJECT_ROOT`. Keep directory and filename
settings aligned when switching datasets. Downloaded receipts are cached at
`COUNCIL_RECEIPTS_PATH`: choose a new path when changing the source release.

## Prepare the data

1. Build a charity register and ONS lookup using the [core guide](../core/README.md),
   or supply existing compatible Parquet files.
2. Copy the chosen register into `data/council_asset_sales/raw/`, retaining its
   timestamped filename, or set `COUNCIL_CHARITY_PATH` to its explicit path.
3. Set `COUNCIL_POSTCODE_LOOKUP_PATH` to the prepared lookup. The default reads
   the existing core output; the council command does not build it.
4. Supply the receipts CSV at `COUNCIL_RECEIPTS_PATH`, or let the command download
   it from `COUNCIL_RECEIPTS_URL`.

When `COUNCIL_CHARITY_PATH` is `None`, selection uses the latest filename matching
`charity_register_YYYYMMDD_HHMMSS_microsecondsZ.parquet` in `COUNCIL_RAW_DIR`.
If no timestamped register exists, it accepts `charity_register.parquet` there.
It does not automatically search core outputs. An explicit missing path fails.

The Excel workbook in `legacy_raw/` is not used by this CSV pipeline. Replacement
inputs must retain the schemas expected by the readers.

## Build the panel

```powershell
uv run python -m uk_charity_local_authority_analysis.council_asset_sales
```

The command prints the output path and replaces the configured panel Parquet.
Unlike core register builds, panel builds do not create timestamped outputs or
JSON run records. Set a different output path to keep multiple versions.

For a query or an in-memory result:

```python
from uk_charity_local_authority_analysis.council_asset_sales.preprocessing import (
    scan_charity_receipts_panel,
    load_charity_receipts_panel,
)

query = scan_charity_receipts_panel(start_year=2018, end_year=2023)
panel = load_charity_receipts_panel(start_year=2018, end_year=2023)
```

## Interpret the output

The panel contains one row per current English local authority, configured
financial year, and configured size category. It includes authority and region
codes/names, receipts in GBP thousands and millions, a `receipt_observed` flag,
receipt lags in GBP millions, and charity removal counts.

- Financial years start in April; 2018 means 2018?19.
- Only submitted LB, MD, SD, and UA receipt records are retained. County and
  special-authority receipts are excluded.
- Retired receipt authority codes are mapped to LAD25 successors and summed.
  This represents LAD-own receipts, not equivalent service coverage across
  reorganisations. Review [`preprocessing/geography.py`](preprocessing/geography.py)
  if changing the geography vintage.
- Missing receipt observations remain null and have `receipt_observed = False`.
  Absent removal counts become zero.
- Lags match exact financial years against the full receipts input, including
  years before the panel starts. Gaps remain null.
- Default charity sizes are Small, Medium, and Large. Unknown-size removals are
  excluded from the default panel. Size definitions come from the input register.

## Folder guide

| Location | Purpose |
| --- | --- |
| `config.py` | All council paths, endpoints, and panel settings |
| `datasets/la_capital_receipts/` | CSV download, schema validation, and loading |
| `preprocessing/capital_receipts.py` | Submitted LAD receipt preparation |
| `preprocessing/geography.py` | LAD25 crosswalk and English authority lookup |
| `preprocessing/panel.py` | Balanced panel, lags, and Parquet output |
| `preprocessing/clean_receipt_legacy.py` | Older in-memory helpers; not the command's pipeline |
| `tests/` | Offline configuration and panel regression tests |

## Tests

```powershell
uv run python -m unittest discover -s src/uk_charity_local_authority_analysis/council_asset_sales -t src -v
```
