# UK charity local authority analysis

Build a UK charity register and analyse charity removals alongside English
local-authority asset disposal receipts.

## Setup

You need Git and `uv`. The project requires Python 3.14 or newer; `uv` manages
the project environment and dependencies.

1. Clone this repository and open a terminal in its root directory.
2. Create the environment and install the locked dependencies:

   ```powershell
   uv sync --locked
   ```

3. Supply the local source datasets and configure the module you want to run.
   The module guides below describe the required files and available downloads.
4. Run commands with `uv run` from the repository root; manual environment
   activation is unnecessary.

Source datasets are not bundled with the repository. Default data locations are
under `data/` and `projects/council_asset_sales/datasets/`, and common dataset
formats are excluded from Git.

## Datasets

Legacy datasets can be found here:
https://drive.google.com/drive/folders/1jLyCxNoDJmrcjkQQYx_yZM3h2lTKfNPy?usp=sharing


## Module guides

| Module              | Guide                                                                                                                               | Default data directory      |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| Core                | [Inputs, charity register builds, ONS lookup, and run records](#charity-register)              | `data/charity_commission_register/`                |
| Council asset sales | [Receipt inputs, charity-removals panel, and interpretation](projects/council_asset_sales/README.md) | `projects/council_asset_sales/datasets/` |

Each module separates processing settings (`config.py`) from local paths
(`filepath.py`). File constants end in `_FILEPATH`; directories end in `_DIR`
(with `PROJECT_ROOT` identifying the repository). Library functions use those
defaults and accept explicit input and output filepath arguments.

Executable scripts live in [`scripts/`](scripts/), with no package initialiser
or `__main__.py`. Each script declares its input and output paths and passes them
to library functions. Edit the script's path block for a particular run; changing
library defaults does not override paths explicitly set in a script. The previous
`python -m` pipeline entry points have been removed.

| Script | Purpose |
| --- | --- |
| [`download_and_extract.py`](scripts/download_and_extract.py) | Download all register sources, or select `ons`, `charity`, `classification`, and/or `company_house` |
| [`build_charity_register.py`](scripts/build_charity_register.py) | Prepare ONS geography and build the legacy-source register |
| [`extract_charity_commission.py`](scripts/extract_charity_commission.py) | Extract the two local JSON archives |

If starting from raw charity sources, build the register first, then follow the
council guide to select inputs for that analysis.

Download and extraction tooling lives in
[`download_and_extract.py`](src/uk_charity_local_authority_analysis/charity_commission_register/download_and_extract.py).
Preparation is grouped by source in `charity_commission.py`, `company_house.py`,
`find_that_charity.py`, and `ons.py` within the register library.
The download script calls its shared `download_file` and `extract_zip` functions. Build and extraction
functions read local files; missing inputs raise an error without a network
request. The standalone scripts remain plain files, not a Python package.

### Download all datasets

From the repository root, run:

```powershell
uv run python scripts/download_and_extract.py
```

To download only certain sources, supply one or more names:

```powershell
uv run python scripts/download_and_extract.py ons
uv run python scripts/download_and_extract.py charity classification
uv run python scripts/download_and_extract.py company_house
```

No source names means all four register sources. The script's `SOURCES` mapping
defines URLs, source directories, and filenames. Every run downloads fresh files, including
reruns on the same day. If a download
fails, the remaining downloads are still attempted, and the command reports the
failed sources and exits with a nonzero status. Rerunning refreshes all selected sources.

The download script uses the local download date in `DDMMYYYY` format, for example
`25052025` for 25 May 2025. Files are saved in these repository-relative folders:

| Source | Download destination |
| --- | --- |
| Charity and classification archives | `data/charity_commission_register/charity_commission/<DDMMYYYY>/` |
| ONS postcode archive | `data/charity_commission_register/ons/<DDMMYYYY>/` |
| Companies House ZIP | `data/charity_commission_register/company_house/<DDMMYYYY>/` |

Extraction and build scripts default to today's download folder. Set their
`DOWNLOAD_DATE` to an older folder name when processing an earlier download.
The build script saves the prepared ONS lookup at `ons/<DDMMYYYY>/ons_postcode_lookup.parquet`; remove that
cached output or choose a new output filepath to rebuild it from a new archive.
Legacy register CSV inputs remain in their legacy folders listed below.

This downloads the ONS ZIP, the two Charity Commission JSON ZIPs, the Companies
House ZIP. Each ZIP is automatically extracted in the
same dated directory, inside a subfolder named after the archive. All archive
files and internal folders are preserved; the ZIP is kept too. Rerunning replaces
the extracted folder after a complete fresh extraction, removing obsolete members
and updating files even if their sizes have not changed. CSV downloads
need no extraction. The single build script prepares ONS and the register. The legacy
CSVs for Charity Commission, Companies House, and Find That Charity still need
to be supplied locally; these downloads do not replace them.

Companies House uses the single-file snapshot linked from its
[download page](https://download.companieshouse.gov.uk/en_output.html), pinned to
`BasicCompanyDataAsOneFile-2026-09-01.zip`. Edit the URL, destination directory,
and filename directly in the `company_house` entry in `scripts/download_and_extract.py`
to select a newer release.
This snapshot covers live companies; its ZIP and extracted CSV are both kept. The register
build continues to use the legacy CSV containing dissolved-company addresses.

## Charity register

Build a charity register from local Charity Commission, Companies House, and
Find That Charity CSVs, enriched with ONS postcode geography. The register is
available to downstream analyses such as council asset sales.

Library code lives in
[`src/uk_charity_local_authority_analysis/charity_commission_register/`](src/uk_charity_local_authority_analysis/charity_commission_register/).
Default input and output files live in
[`data/charity_commission_register/`](data/charity_commission_register/). Default register inputs are listed in
[`filepath.py`](src/uk_charity_local_authority_analysis/charity_commission_register/filepath.py).

### Configure inputs

Processing settings, including income thresholds, category mappings, and source
URLs, live in [`config.py`](src/uk_charity_local_authority_analysis/charity_commission_register/config.py).
Default paths live in [`filepath.py`](src/uk_charity_local_authority_analysis/charity_commission_register/filepath.py).
Restart Python after editing either module. For command-line runs, edit the
explicit filepath assignments in the selected script.

| Source or output | Default filepath constants |
| --- | --- |
| Charity Commission legacy CSVs | `CHARITY_FILEPATH`, `CHARITY_CLASSIFICATION_FILEPATH` |
| Companies House | `COMPANY_HOUSE_FILEPATH` |
| Find That Charity | `FIND_THAT_CHARITY_FILEPATH` |
| ONS archive and optional standalone CSV | `ONS_ARCHIVE_FILEPATH`, `ONS_SOURCE_CSV_FILEPATH` |
| Prepared ONS lookup | `ONS_LOOKUP_FILEPATH` |
| Register output basename | `CHARITY_REGISTER_FILEPATH` |
| Official Charity Commission archives | `CHARITY_COMMISSION_CHARITY_ARCHIVE_FILEPATH`, `CHARITY_COMMISSION_CLASSIFICATION_ARCHIVE_FILEPATH` |

Charity Commission and Companies House legacy data use their `28052025_legacy`
subfolders. Find That Charity uses
[`find_that_charity_28052025_legacy/`](data/charity_commission_register/find_that_charity_28052025_legacy/)
directly under `data/charity_commission_register/`, containing
`find_that_charity_28052025.csv`. These 28 May 2025 files are the last files we downloaded
from those sources that include addresses for dissolved charities, so they remain
the default inputs for the register build.

The defaults also select the May 2026 ONS release. Supply the legacy CSVs locally.
Official JSON downloads for
charity and classification data are available through the
[Charity Commission downloader](#charity-commission-downloads).
To choose different data, change the directory and filenames together:

```python
CHARITY_COMMISSION_DIR = DEFAULT_DATA_DIR / "charity_commission" / "raw"
CHARITY_FILEPATH = CHARITY_COMMISSION_DIR / "charity_commission_latest.csv"
CHARITY_CLASSIFICATION_FILEPATH = CHARITY_COMMISSION_DIR / "charity_classification_latest.csv"

# Absolute directories also work.
COMPANY_HOUSE_DIR = Path("D:/datasets/companies")
COMPANY_HOUSE_FILEPATH = COMPANY_HOUSE_DIR / "companies.csv"
```

Anchor repo-relative paths to `PROJECT_ROOT` or `DEFAULT_DATA_DIR`. Replacement
CSVs must retain the columns expected by the pipeline.

For ONS, change the item ID or supply a direct compatible ZIP URL. Keep the ZIP
filename aligned with the release. The download command refreshes ZIPs and extracted
files on every run. ONS Parquet builds still reuse existing outputs: choose a new
output path or remove the cached Parquet when switching releases.

Leave `ONS_SOURCE_CSV_FILEPATH = None` to use the archive and geography name lookups, or
set it to a local CSV path. A configured CSV rebuilds the ONS Parquet on each
build and supplies geography codes with null names; it does not affect the
download and extraction functions.

### Run

Run these commands from the repository root after completing the
[setup guide](#setup).

With the legacy CSVs supplied locally, run these steps in order. Skip the
download when the ONS archive is already available:

```powershell
uv run python scripts/download_and_extract.py ons
uv run python scripts/build_charity_register.py
```

The build script prepares or reuses the ONS lookup and saves a timestamped
register. Set `DOWNLOAD_DATE`
in its path block when using older downloads. Existing ONS Parquet outputs are
reused; choose a new output path or remove the cached lookup to rebuild it.

| Library function | Result under the default `data\charity_commission_register\ons` directory |
| --- | --- |
| `extract_ons_postcode_lookup` | Extract the postcode, LAD, and region CSVs from a local ZIP |
| `build_ons_postcode_lookup` | Create `ons_postcode_lookup.parquet` with postcode, LAD, and region codes/names |

The register library function reads a supplied ONS Parquet directly; the script
prepares it first. Custom library use:

```python
from pathlib import Path
from uk_charity_local_authority_analysis.charity_commission_register import build_charity_register

saved = build_charity_register(
    output_path=Path("custom/output/register.parquet"),
    charity_filepath=Path("custom/charity.csv"),
    classification_filepath=Path("custom/classification.csv"),
    company_house_filepath=Path("custom/companies.csv"),
    find_that_charity_filepath=Path("custom/find_that_charity.csv"),
    ons_filepath=Path("custom/ons_lookup.parquet"),
)
```

### Outputs and run records

Each successful register build saves two files beside the configured
`CHARITY_REGISTER_FILEPATH`. By default:

```text
data/charity_commission_register/output/
  charity_register_20260906_143025_123456Z.parquet
  charity_register_20260906_143025_123456Z.run.json
```

The suffix is the run's UTC start time, including microseconds (`Z` means UTC).
Previous runs are preserved, including when timestamps collide. The command
prints the Parquet path and logs the JSON path.

The JSON records:

- UTC start and completion times.
- Input dataset paths, sizes, and modification timestamps.
- The actual prepared ONS filepath used by the register build.
- Saved Parquet path, size, and row/column counts.

Records describe successful builds only; older outputs are not backfilled.
They contain file metadata, not copies or hashes of the inputs. The register run record does not infer the upstream origin of the supplied ONS file.
If record publication fails, the new Parquet is removed and the build reports
an error.

### Analyse removals

```python
from pathlib import Path
from uk_charity_local_authority_analysis.charity_commission_register.build_charity_register import scan_charity_removals

# Latest timestamped run; falls back to the old unsuffixed file if necessary.
removals = scan_charity_removals().collect()

# Or select a specific run.
removals = scan_charity_removals(
    Path("data/charity_commission_register/output/charity_register_20260906_143025_123456Z.parquet")
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

### Library folder guide

Source locations below are relative to
`src/uk_charity_local_authority_analysis/charity_commission_register/`;
tests are relative to the repository root.

| Location | Purpose |
| --- | --- |
| `config.py` | Income thresholds, category mappings, and source URLs |
| `filepath.py` | Explicitly named default input and output filepaths |
| `build_charity_register.py` | Merge prepared sources, save register runs, and aggregate removals |
| `download_and_extract.py` | File downloads and generic ZIP extraction |
| `charity_commission.py` | Charity Commission archive extraction, CSV loading, and charity/classification cleaning |
| `company_house.py` | Companies House CSV loading and company-number normalisation |
| `find_that_charity.py` | Find That Charity CSV loading and cleaning |
| `ons.py` | ONS archive extraction, lookup preparation, and register geography |
| [`tests/charity_commission_register/`](tests/charity_commission_register/) | Library tests, organised by module outside `src/` |

### Charity register tests

Run the core tests from the repository root:

```powershell
uv run python -m unittest discover -s tests/charity_commission_register -t . -v
```

## Charity Commission downloads

Download the two JSON archives linked from the
[full register download page](https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download):

- [Charity](https://ccewuksprdoneregsadata1.blob.core.windows.net/data/json/publicextract.charity.zip)
- [Charity classification](https://ccewuksprdoneregsadata1.blob.core.windows.net/data/json/publicextract.charity_classification.zip)

Run from the repository root:

```powershell
uv run python scripts/download_and_extract.py charity classification
```

The download script fetches and extracts the selected archives. Files are under
`data/charity_commission_register/charity_commission/<DDMMYYYY>/`.
Each ZIP has an adjacent archive-named folder containing its original JSON file.
The optional `scripts/extract_charity_commission.py` command can re-extract local
archives with explicitly configured JSON output paths.

Downloads refresh ZIPs and extracted files even on same-day reruns. To keep a new
snapshot, run the download script on a new date. To extract an earlier snapshot,
set the extraction script's `DOWNLOAD_DATE` to that folder name. The two requests
are independent and do not guarantee that upstream data was published at the
same instant. Download URLs live in the library `config.py`.

```python
from pathlib import Path
from uk_charity_local_authority_analysis.charity_commission_register.charity_commission import (
    extract_charity_commission,
)

sources = extract_charity_commission(Path("data/charity_commission_register/charity_commission/25052025"))
print(sources.charity, sources.classification)
```

This library module extracts local source JSON; it does not convert it to the
legacy CSV schema or change the register builder's configured inputs.
It shares the safe local extraction helpers with ONS. Download caching and
atomic file publication are implemented in `download_and_extract.py`.

Offline tests live in `tests/charity_commission_register/datasets/charity_commission/`:

```powershell
uv run python -m unittest discover -s tests/charity_commission_register/datasets/charity_commission -t . -v
```

## Notebooks

Exploratory notebooks live under `projects/council_asset_sales/notebooks/` and read from
that module's prepared outputs (for example `projects/council_asset_sales/datasets/raw/`
and `projects/council_asset_sales/datasets/output/`). Notebook dependencies (Jupyter,
pandas, matplotlib, statsmodels, seaborn, pyarrow) are kept out of the base
install and live in the `notebooks` dependency group:

```powershell
uv sync --group notebooks
```

Launch Jupyter from the repository root with `uv run jupyter lab` (or
`jupyter notebook`), then open a notebook under `projects/council_asset_sales/notebooks/`. Build the
relevant module's outputs first, and restart the kernel after editing a
module's `config.py` or `filepath.py`.

## Tests

Tests for code under `src/` live in the top-level `tests/` folder, organised by
module. Council asset sales tests remain in `projects/council_asset_sales/tests/`.
Download tests live in `tests/charity_commission_register/test_download.py` and
are included in the main suite. Run each suite separately:

```powershell
uv run python -m unittest discover -s tests -t . -v
uv run python -m unittest discover -s projects/council_asset_sales/tests -t . -v
```

Each module guide also includes a command for running only that module's tests.
