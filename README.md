# UK charity local authority analysis

Build an England and Wales charity register with postcode geography, then analyse
charity removals alongside English local-authority asset disposal receipts. The
council asset sales project also adds upper-tier local authority (UTLA) codes and
names to charity records.

## Setup

Clone the repository and run all commands from its root. You need Git and `uv`;
the project requires Python 3.14 or newer.

```powershell
uv sync --locked
```

Use `uv run` for commands; environment activation is unnecessary. For notebooks:

```powershell
uv sync --locked --group notebooks
uv run --group notebooks jupyter lab
```

Source datasets and generated outputs are excluded from Git, including CSV,
Parquet, JSON, Excel and ZIP files. Supply local inputs before building. The
[legacy dataset folder](https://drive.google.com/drive/folders/1jLyCxNoDJmrcjkQQYx_yZM3h2lTKfNPy?usp=sharing)
is the existing shared location for legacy sources.

## Choose a workflow

| Workflow | Inputs | Output | Guide |
| --- | --- | --- | --- |
| Core charity register | Legacy charity, classification, company and Find That Charity CSVs; ONS postcode data | Register with `charity_postcode` and `local_authority_code` | [Build the register](#build-the-charity-register) |
| Council receipts panel | Project-local register, receipts CSV and prepared ONS lookup | English LAD/year/charity-size panel | [Council panel](projects/council_asset_sales/README.md#build-the-receipts-panel) |
| Charity asset register | Project-local register and postcode-to-UTLA lookup | Charity records with `UTLA` and `UTLA_NAME` | [UTLA enrichment](projects/council_asset_sales/README.md#build-the-charity-asset-register) |

LAD means local authority district. The panel uses LAD geography; the asset
register adds UTLA geography through a separate postcode lookup.

## Repository layout

```text
scripts/                                Core download and build commands
src/uk_charity_local_authority_analysis/
  charity_commission_register/          Shared register and source preparation
data/charity_commission_register/        Local core inputs and outputs
projects/council_asset_sales/
  scripts/                              Project download and build commands
  pipeline/                             Receipts, geography, panel and UTLA processing
  datasets/                             Project inputs and outputs
  notebooks/                            Charity, receipts and regression analysis
tests/                                  Shared library tests
```

Library settings live in
[`config.py`](src/uk_charity_local_authority_analysis/charity_commission_register/config.py)
and default paths in
[`filepath.py`](src/uk_charity_local_authority_analysis/charity_commission_register/filepath.py).
Core scripts declare explicit paths for each run; edit those assignments to
change their inputs. Library functions also accept explicit filepaths. Restart
Python or the notebook kernel after changing imported settings.

## Build the charity register

### 1. Supply the legacy CSV inputs

The default build uses these files under `data/charity_commission_register/`:

| Source | Relative path |
| --- | --- |
| Charity Commission | `charity_commission/28052025_legacy/charity_commission_28052025.csv` |
| Charity classifications | `charity_commission/28052025_legacy/charity_classification_28052025.csv` |
| Companies House | `company_house/28052025_legacy/company_house_28052025.csv` |
| Find That Charity | `find_that_charity_28052025_legacy/find_that_charity_28052025.csv` |

These legacy snapshots retain address information needed for removed charities
and dissolved companies. Edit the input block in
[`scripts/build_charity_register.py`](scripts/build_charity_register.py) to use
different files with the expected columns.

The official JSON archives and Companies House snapshot available through the
downloader are separate sources. Downloading them does not convert or replace
the legacy CSV inputs used by this build.

### 2. Prepare ONS data and build

```powershell
uv run python scripts/download_and_extract.py ons
uv run python scripts/build_charity_register.py
```

Skip downloading when the desired ONS archive is already local. The build script
defaults to today's download folder; set its `DOWNLOAD_DATE` to the existing
folder's `DDMMYYYY` date when using an earlier download.

The configured release is `ONSPD_MAY_2026.zip`. The build prepares postcode,
LAD and region codes/names in:

```text
data/charity_commission_register/ons/<DDMMYYYY>/ons_postcode_lookup.parquet
```

An existing prepared lookup is reused. Choose a new output path or remove the
cached lookup when rebuilding from a changed archive. Setting
`ONS_SOURCE_CSV_FILEPATH` to a compatible standalone ONS CSV rebuilds the lookup
on each run, with geography codes but null names.

### 3. Use the outputs

Each successful build writes a new pair under
`data/charity_commission_register/output/`:

```text
charity_register_<YYYYMMDD_HHMMSS_microsecondsZ>.parquet
charity_register_<YYYYMMDD_HHMMSS_microsecondsZ>.run.json
```

The timestamp is the UTC run start time. Earlier runs are preserved. The JSON
records start/completion times, input paths and file metadata, the prepared ONS
path, and output dimensions. It records metadata rather than input contents or
hashes.

For council analysis, place the selected register in the project's
`datasets/charity_register_inputs/` folder as described in the
[council guide](projects/council_asset_sales/README.md#prepare-the-project-inputs).

### Register conventions

- Main charity records use `linked_charity_number = 0`; Find That Charity is
  restricted to `ccew`. Linked-fund classifications contribute to the parent
  charity, and missing classification flags become zero.
- Company numbers remain strings; numeric identifiers are padded to eight
  characters. Source joins validate lookup uniqueness.
- `charity_postcode` uses the first available postcode from Companies House
  (`RegAddress.PostCode`), Charity Commission (`charity_contact_postcode`), then
  Find That Charity (`postalCode`). It is matched to ONS to obtain
  `local_authority_code`; an unmatched postcode leaves that code null.
- Financial years start in April. Income bands are Small below GBP 25,000,
  Medium from GBP 25,000 through GBP 1,000,000, and Large above GBP 1,000,000.
  Missing income leaves size unclassified.
- Geography follows the selected ONS release, rather than historical boundaries
  for each removal date.

To aggregate removals from the latest core register:

```python
from uk_charity_local_authority_analysis.charity_commission_register.build_charity_register import (
    scan_charity_removals,
)

removals = scan_charity_removals().collect()
```

Pass a specific register `Path` to select another run. Results group by
`local_authority_code`, `financial_year` and `size_category`. Missing sizes are
labelled `Unknown`; records without a local authority or removal year are excluded.

## Download source snapshots

[`scripts/download_and_extract.py`](scripts/download_and_extract.py) accepts
one or more source names. Omitting names downloads all four:

```powershell
uv run python scripts/download_and_extract.py
uv run python scripts/download_and_extract.py charity classification
uv run python scripts/download_and_extract.py company_house
```

| Source name | Configured download | Folder under `data/charity_commission_register/` |
| --- | --- | --- |
| `ons` | May 2026 ONS postcode directory | `ons/<DDMMYYYY>/` |
| `charity` | Charity Commission charity JSON ZIP | `charity_commission/<DDMMYYYY>/` |
| `classification` | Charity Commission classification JSON ZIP | `charity_commission/<DDMMYYYY>/` |
| `company_house` | `BasicCompanyDataAsOneFile-2026-09-01.zip` | `company_house/<DDMMYYYY>/` |

The folder date is the local download date, not the source's publication date.
Every run refreshes selected downloads, including same-day reruns. ZIPs are
retained and extracted into adjacent archive-named folders; extraction replaces
the previous folder after a successful fresh extraction. Failed sources are
reported after the remaining selections are attempted, and the command exits
with a nonzero status.

Edit the script's `SOURCES` mapping and the referenced URLs in library `config.py`
to change releases. Keep archive filenames and build paths aligned. Build
functions read local data and do not initiate downloads.

Council receipts and UTLA downloads have their own
[project commands](projects/council_asset_sales/README.md).

## Notebooks

The [council notebooks](projects/council_asset_sales/notebooks/) contain:

- `charity.ipynb`: charity register exploration, counts and trends.
- `receipt.ipynb`: disposal receipts from the prepared council panel.
- `regression.ipynb`: analysis using the prepared council panel.

Install the `notebooks` dependency group using the [setup commands](#setup).
Select the project register before opening the charity notebook, and build the
panel before running the receipts or regression notebooks.

## Tests

Run the committed shared-library tests from the repository root:

```powershell
uv run python -m unittest discover -s tests -t . -v
```

Tests are organised under
[`tests/charity_commission_register/`](tests/charity_commission_register/), including
download, extraction, source preparation and register behaviour.
