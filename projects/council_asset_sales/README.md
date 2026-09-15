# Council asset sales

Build two datasets from a selected charity register:

| Dataset | Purpose | Geography |
| --- | --- | --- |
| Charity receipts panel | Relate charity removals to asset disposal receipts by financial year and charity size | English local authority districts (LAD25) |
| Charity asset register | Add `UTLA` and `UTLA_NAME` to charity records | November 2023 postcodes mapped to 2022 upper-tier local authorities |

These are separate builds. Adding UTLA columns does not change the panel's LAD
grouping or receipt coverage.

## Prepare the project inputs

Follow the repository [setup guide](../../README.md#setup). Run all commands from
the repository root. Paths starting with `datasets/` below are relative to
`projects/council_asset_sales/`.

Place a prepared charity register in `datasets/charity_register_inputs/`:

```text
datasets/charity_register_inputs/
  charity_register_<YYYYMMDD_HHMMSS_microsecondsZ>.parquet
```

Copy a selected output from the [core register build](../../README.md#build-the-charity-register),
or supply a compatible register. Project commands select from this input folder
by default; they do not automatically copy the core output. The latest
timestamped register is selected, falling back to `charity_register.parquet`
when no timestamped run exists.

The panel and charity notebook share the register settings in
[`filepath.py`](filepath.py). The asset builder has its own overrides in
[`scripts/build_charity_asset_register.py`](scripts/build_charity_asset_register.py).
Pin both when they should use the same specific snapshot.

## Build the receipts panel

### Inputs and commands

| Input | Default selection |
| --- | --- |
| Charity register | Latest register in `datasets/charity_register_inputs/` |
| Receipts CSV | Latest dated `datasets/la_receipts/<DDMMYYYY>/la_receipts.csv` |
| Prepared ONS lookup | Latest dated `data/charity_commission_register/ons/<DDMMYYYY>/ons_postcode_lookup.parquet` at repository root |

Prepare the ONS lookup using the [core workflow](../../README.md#build-the-charity-register)
if it is missing. The panel command reads existing local inputs; it does not
rebuild the register or ONS lookup.

```powershell
uv run python projects/council_asset_sales/scripts/download.py
uv run python projects/council_asset_sales/scripts/build.py
```

The downloader refreshes the receipts CSV on every run and saves it in today's
local `DDMMYYYY` folder. Skip it when the desired snapshot is already available.
The source URL and publication reference are in [`config.py`](config.py).

### Settings

Edit [`config.py`](config.py) for analysis settings:

| Setting | Default |
| --- | --- |
| `PANEL_START_YEAR` | `2018` |
| `PANEL_END_YEAR` | `2023`, inclusive |
| `CHARITY_SIZE_CATEGORIES` | `Small`, `Medium`, `Large` |
| `LA_RECEIPTS_LAG_PERIODS` | `1`, `2`, `3` years |

Edit [`filepath.py`](filepath.py) to pin inputs or change the output:

- `CHARITY_REGISTER_FILEPATH`: a specific register; `None` selects the latest
  beside `CHARITY_REGISTER_BASE_FILEPATH`.
- `LA_RECEIPTS_FILEPATH`: selected receipts CSV.
- `ONS_LOOKUP_FILEPATH`: prepared ONS lookup defining English LADs and names.
- `CHARITY_LA_RECEIPTS_PANEL_FILEPATH`: output basename.

Dated files are selected by calendar date, ignoring folders such as
`15072025_legacy`. If none exists, the default points to today's expected file
and loading reports the missing input. Restart Python or the notebook kernel
after changing imported settings, then rebuild the panel.

Library functions accept explicit input paths and year overrides:

```python
from projects.council_asset_sales.pipeline import load_charity_la_receipts_panel

panel = load_charity_la_receipts_panel(start_year=2018, end_year=2023)
```

### Output and interpretation

Each build writes:

```text
datasets/output/charity_la_receipts_panel_<YYYYMMDD_HHMMSS_microsecondsZ>.parquet
```

There is one row per English LAD in the configured ONS lookup, financial year
and charity size category.

| Columns | Meaning |
| --- | --- |
| `local_authority_code`, `local_authority` | LAD code and name |
| `region_code`, `region_name` | Region code and name |
| `financial_year` | April-start year's first calendar year; `2018` means 2018/19 |
| `charity_size_category` | Input register's `size_category`, renamed |
| `la_capital_receipts_gbp_thousands`, `la_capital_receipts_gbp_millions` | Tangible fixed-asset disposal receipts |
| `la_receipt_observed` | Whether a prepared receipt observation exists |
| `la_capital_receipts_gbp_millions_lag1` through `lag3` | Default exact-year receipt lags |
| `removals` | Charity removal count |

- Receipts include submitted London borough (`LB`), metropolitan district
  (`MD`), shire district (`SD`) and unitary authority (`UA`) records.
  County and special-authority receipts are excluded.
- Retired receipt codes map to LAD25 successors and are summed using
  [`pipeline/geography.py`](pipeline/geography.py). These are the LADs' own
  receipts; predecessor district sums do not represent equivalent service
  coverage after reorganisation into unitary authorities.
- Missing receipt observations remain null with `la_receipt_observed = False`.
  Missing removal counts become zero. Unknown-size removals are excluded from
  the default size categories.
- Lags match exact financial years across the full receipts input, including
  years before the panel starts. A missing year leaves a null lag.
- Receipt values repeat across charity size categories. Deduplicate by LAD and
  year before summing receipts.

## Build the charity asset register

The asset register uses the project charity register and a separate ONS
postcode-to-UTLA CSV. The downloader is configured for
`PCD_OA21_LSOA21_MSOA21_LTLA22_UTLA22_CAUTH22_NOV23_UK_LU_V2.zip`.

```powershell
uv run python projects/council_asset_sales/scripts/download_utla_lookup.py
uv run python projects/council_asset_sales/scripts/build_charity_asset_register.py
```

Downloads are refreshed and extracted into `datasets/utla_lookup/<DDMMYYYY>/`.
The date identifies the download snapshot; the lookup still uses November 2023
postcode coverage and 2022 UTLA geography.

### Matching logic

[`pipeline/charity_asset_register.py`](pipeline/charity_asset_register.py)
left-joins the register's `charity_postcode` to the lookup's `pcds`, ignoring
case and whitespace. It adds:

| Lookup column | Output column |
| --- | --- |
| `utla22cd` | `UTLA` |
| `utla22nm` | `UTLA_NAME` |

LAD codes, charity names and charity identifiers are not join keys. In a
core-built register, `charity_postcode` already follows the Companies House,
Charity Commission, then Find That Charity postcode priority.

All input rows and their order are retained. Unmatched postcodes receive null
UTLA values. Identical mappings are deduplicated; conflicting postcode mappings
fail join validation. Inputs already containing `UTLA` or `UTLA_NAME` are rejected.

### Configure and save

Edit [`scripts/build_charity_asset_register.py`](scripts/build_charity_asset_register.py):

| Setting | Behaviour |
| --- | --- |
| `CHARITY_FILEPATH` | `None` selects the latest register beside `CHARITY_BASE_FILEPATH`; set a path to pin it |
| `UTLA_LOOKUP_FILEPATH` | `None` selects the configured CSV filename in the newest dated UTLA folder; set a path to pin it |
| `COLUMNS_TO_KEEP` | Ordered output column list; `None` retains every input column plus the UTLA columns |
| `OUTPUT_FILEPATH` | Output basename |

The default column list enumerates the expected register schema. Update it or
use `None` when input columns change. Each build writes:

```text
datasets/output/charity_asset_register_<YYYYMMDD_HHMMSS_microsecondsZ>.parquet
```

Both project builders use UTC run timestamps, preserve earlier outputs and leave
source registers unchanged. They write Parquet files; the core register builder
also writes a `.run.json` record.

## Notebooks

Install notebook dependencies and launch Jupyter from the repository root:

```powershell
uv sync --locked --group notebooks
uv run --group notebooks jupyter lab
```

| Notebook | Input |
| --- | --- |
| [`charity.ipynb`](notebooks/charity.ipynb) | Project register selected through `filepath.py` |
| [`receipt.ipynb`](notebooks/receipt.ipynb) | Latest completed receipts panel |
| [`regression.ipynb`](notebooks/regression.ipynb) | Latest completed receipts panel |

Build the panel before opening the receipts and regression notebooks. Rebuild
after changing the register or panel settings so they use the intended snapshot.

## Code and data locations

| Location | Purpose |
| --- | --- |
| [`scripts/`](scripts/) | Downloads and builds |
| [`pipeline/charity_asset_register.py`](pipeline/charity_asset_register.py) | UTLA join and asset register output |
| [`pipeline/la_receipts.py`](pipeline/la_receipts.py) | Receipts CSV loading and validation |
| [`pipeline/la_capital_receipts.py`](pipeline/la_capital_receipts.py) | Submitted LAD receipts and units |
| [`pipeline/geography.py`](pipeline/geography.py) | LAD25 crosswalk and English geography |
| [`pipeline/panel.py`](pipeline/panel.py) | Panel, lags and timestamped output |
| [`pipeline/legacy/`](pipeline/legacy/) | Older helpers, unused by current commands |
| `datasets/charity_register_inputs/` | Selected project charity registers |
| `datasets/la_receipts/` | Dated receipts CSVs and legacy inputs |
| `datasets/utla_lookup/` | Dated postcode-to-UTLA downloads |
| `datasets/output/` | Generated panels and asset registers |

For shared library tests, see the repository [test guide](../../README.md#tests).
