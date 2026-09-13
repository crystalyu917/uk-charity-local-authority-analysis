# Council asset sales

Build an English local-authority, financial-year, and charity-size panel linking
LA receipts to charity removals. All commands and receipt data for this project
live in this folder. Charity registers are read from the project's
`datasets/charity_register_inputs/`; the ONS lookup comes from the shared dated outputs.

## Run

From the repository root, with the project environment installed:

```powershell
uv run python projects/council_asset_sales/scripts/download.py
uv run python projects/council_asset_sales/scripts/build.py
```

The download command refreshes the CSV on every run, including same-day reruns,
and saves `datasets/la_receipts/<DDMMYYYY>/la_receipts.csv` within this project.
Skip downloading if the desired local CSV is already available.

The build command requires an existing charity register and prepared ONS lookup.
It writes a new file such as
`datasets/output/charity_la_receipts_panel_20260913_190530_123456Z.parquet`.
The suffix is the UTC run start date and time, including microseconds. Earlier
runs are preserved; notebooks select the latest completed panel.
It does not download data or rebuild the shared register or ONS files.

## Inputs and settings

### Charity asset register with UTLA

```powershell
uv run python projects/council_asset_sales/scripts/download_utla_lookup.py
uv run python projects/council_asset_sales/scripts/build_charity_asset_register.py
```

The downloader refreshes and extracts the
[postcode-to-UTLA lookup](https://www.arcgis.com/sharing/rest/content/items/bc8f6d1f6ee64111b6a59b22c6605f3b/data)
under `datasets/utla_lookup/<DDMMYYYY>/`. This is November 2023 postcode coverage
mapped to 2022 upper-tier authorities, not current-year geography.

The asset builder reads only `datasets/charity_register_inputs/` for its charity
register. It joins `charity_postcode` to the lookup's `pcds`, ignoring case and
spaces. `UTLA` contains `utla22cd`, the official authority code; `UTLA_NAME` contains its `utla22nm` name. All charity rows
are retained; unmatched postcodes have null UTLA. Conflicting postcode mappings
raise an error instead of duplicating charity rows.

Edit `COLUMNS_TO_KEEP` in `scripts/build_charity_asset_register.py` to select
columns; it initially lists all 127 current register columns plus UTLA and UTLA_NAME. Set it
to `None` to automatically retain every column in future inputs. Input path
overrides are also at the top of that script.

Output is `datasets/output/charity_asset_register_<YYYYMMDD_HHMMSS_microsecondsZ>.parquet`.
Timestamps use UTC and previous runs are preserved.

### Panel settings

Edit `config.py` for the LA receipts URL and panel settings. Edit `filepath.py`
to pin specific input files or change the output location. Restart Python or the
notebook kernel after editing settings.

`CHARITY_SIZE_CATEGORIES` selects charity income groups from the register.
`PANEL_START_YEAR` and `PANEL_END_YEAR` define the analysis period;
`LA_RECEIPTS_LAG_PERIODS` defines the local-authority receipt lags. The shared
register's `size_category` is renamed to `charity_size_category` in the panel.
Receipt columns use `la_capital_receipts_` and the observation flag is
`la_receipt_observed`. Rebuild the panel before using the updated notebooks;
older panel files retain their original column names.

- `LA_RECEIPTS_FILEPATH` selects the newest dated folder containing `la_receipts.csv`.
- `CHARITY_REGISTER_BASE_FILEPATH` points to `datasets/charity_register_inputs/charity_register.parquet`
  within this project. The newest timestamped register beside that
  basename is selected. Set `CHARITY_REGISTER_FILEPATH` to pin a particular file.
- `ONS_LOOKUP_FILEPATH` selects the newest dated folder containing
  `ons_postcode_lookup.parquet` under `data/charity_commission_register/ons/`.
- `CHARITY_LA_RECEIPTS_PANEL_FILEPATH` sets the output basename; each build appends its run timestamp.

Dates are compared as calendar dates, not alphabetically. If no dated input
exists, its default points to today's folder and loading reports the missing file.
Explicit input overrides are accepted by the panel library functions.

```python
from projects.council_asset_sales.pipeline import load_charity_la_receipts_panel

panel = load_charity_la_receipts_panel(start_year=2018, end_year=2023)
```

Notebooks under `notebooks/` use the same configured register and panel locations.
The charity notebook reads the local register directly. Rebuild the panel after
changing local register inputs so receipt and regression notebooks use that snapshot.
They require the repository's notebook dependencies. Build the panel before
running the receipt and regression notebooks.

## Interpret the output

The panel contains one row per current English local authority, configured
financial year, and configured size category. It includes authority and region
codes/names, receipts in GBP thousands and millions, a `la_receipt_observed` flag,
receipt lags in GBP millions, and charity removal counts.

- Financial years start in April; 2018 means 2018–19.
- Only submitted LB, MD, SD, and UA receipt records are retained. County and
  special-authority receipts are excluded.
- Retired receipt authority codes are mapped to LAD25 successors and summed.
  This represents LAD-own receipts, not equivalent service coverage across
  reorganisations. Review [`pipeline/geography.py`](pipeline/geography.py)
  if changing the geography vintage.
- Missing receipt observations remain null and have `la_receipt_observed = False`.
  Absent removal counts become zero.
- Lags match exact financial years against the full receipts input, including
  years before the panel starts. Gaps remain null.
- Default charity sizes are Small, Medium, and Large. Unknown-size removals are
  excluded from the default panel. Size definitions come from the input register.

## Folder guide

| Location | Purpose |
| --- | --- |
| `scripts/download.py` | Refresh the LA receipts CSV |
| `scripts/build.py` | Build the analysis panel from local inputs |
| `pipeline/la_receipts.py` | Validate required columns and load the receipts CSV |
| `config.py` | Source URL and panel settings |
| `filepath.py` | Project outputs and shared input locations |
| `datasets/la_receipts/` | Receipts snapshots grouped by download date |
| `pipeline/la_capital_receipts.py` | Prepare submitted local-authority receipts |
| `pipeline/geography.py` | LAD25 crosswalk and English authority lookup |
| `pipeline/panel.py` | Balanced panel, lags, and Parquet output |
| [`pipeline/legacy/`](pipeline/legacy/) | Older receipt-cleaning helpers; unused by current commands |
| [`datasets/la_receipts/15072025_legacy/`](datasets/la_receipts/15072025_legacy/) | Older Excel receipts; excluded from dated CSV selection |
| [`datasets/charity_register_inputs/`](datasets/charity_register_inputs/) | Charity register inputs used by notebooks and panel builds |
