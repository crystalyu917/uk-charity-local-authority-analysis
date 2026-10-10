# UK charity local authority analysis

This repository contains data pipelines and analytical projects for studying
registered charities in England and Wales and their relationship with local
authorities.

The core dataset pipeline combines key sources such as Charity
Commission records, Companies House filings, Find That Charity data, and ONS
postcode geography into a single register. This register can be extended with
additional datasets as the project develops and provides charity
characteristics, operational dates, financial information, and local authority
mappings. Other work, including analysis built on this register, is organised
under `projects/`.

The repository includes both a latest charity register and a legacy register.
The latest source data no longer includes addresses for charities that have
been removed from the register. Because these addresses are still needed for
some analyses, the legacy build target and legacy datasets are retained. The
legacy dataset is the most recent downloaded dataset that still contains this
information. It is available in the [shared legacy dataset folder](https://drive.google.com/drive/folders/1jLyCxNoDJmrcjkQQYx_yZM3h2lTKfNPy?usp=sharing).

## Repository structure

```text
.
├── data/                    # Source datasets, staging files, and generated outputs
├── projects/                # Analysis projects and project-specific workflows
│   ├── charity_lease/       # Charity land and lease analysis
│   └── council_asset_sales/ # Council asset sales impact on charity analysis
├── scripts/                 # Commands for downloading data and building the register
├── src/                     # Reusable package code for the register pipeline
├── tests/                   # Automated tests for the shared library
├── pyproject.toml           # Project metadata and dependencies
└── README.md                # Project documentation
```


## Set up the environment

Run commands from the repository root with Python 3.14 or newer and `uv` installed:

```powershell
uv sync --locked --all-packages --all-groups
```

This installs the root package, both analysis projects, and their dependencies.
All three packages share one `uv.lock` and `.venv` in a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/).

## Choose a workflow

The repository has one shared data pipeline at the root and two analysis projects
under `projects/`. Run the commands below from the repository root.

| Workflow | Location | Purpose |
| --- | --- | --- |
| Root charity register pipeline | `scripts/` and `src/` | Download source datasets and build the shared charity register. |
| Charity lease project | `projects/charity_lease/` | Match a prepared charity register to property and lease records, then estimate remaining lease terms. |
| Council asset sales project | `projects/council_asset_sales/` | Download council receipts and build a panel relating asset disposal receipts to charity removals. |

### Root: download and build the charity register

The root workflow runs Python scripts directly:

```powershell
# Show options for downloading the shared source datasets
uv run python scripts/download_and_extract.py --help

# Show options for building the shared charity register
uv run python scripts/build_charity_register.py --help
```

Follow [Download dataset](#download-dataset) and [Build the register](#build-the-register)
below to run this workflow and configure its inputs.

### Project 1: charity lease

`--package charity-lease` selects the package in `projects/charity_lease/`:

```powershell
# Show options for matching charities to property and lease records
uv run --package charity-lease charity-lease-match --help

# Show options for adding remaining lease term estimates to matched records
uv run --package charity-lease charity-lease-terms --help
```

See the [charity lease README](projects/charity_lease/README.md) for inputs and usage.

### Project 2: council asset sales

`--package council-asset-sales` selects the package in `projects/council_asset_sales/`:

```powershell
# Show options for downloading council receipts
uv run --package council-asset-sales council-asset-sales-download --help

# Show options for building the council receipts and charity removals panel
uv run --package council-asset-sales council-asset-sales-build --help
```

See the [council asset sales README](projects/council_asset_sales/README.md) for inputs and usage.

The `--help` commands above display usage without running a download or build.
Both analysis projects require a prepared charity register in their own
`datasets/charity_register_inputs/` folder; copy a selected root output there or
supply a compatible register as described in each project's README.

### Working with the shared environment

Inside either project directory, `uv run <command>` selects that member directly.
Use `uv run --all-packages --group notebooks jupyter lab` for notebooks that import
the project packages. Run `uv lock` after changing any member's dependencies.
Project data stays in its existing directories, outside the packages; default
data paths assume uv's editable workspace installation in this checkout.


## Download dataset

Run commands from the repository root. Pass source names as arguments to
download only the datasets you need:

```powershell
# Download every configured source
uv run python scripts/download_and_extract.py

# Download selected sources, for example geography only
uv run python scripts/download_and_extract.py onspd utla
```

The available source names are `onspd`, `utla`, `charity`, `classification`,
and `company_house`. If no names are supplied, all configured sources are
downloaded. Files are saved under their configured source directory in a folder
named with the local download date (`DDMMYYYY`), and ZIP files are extracted
there automatically.

The two geography sources serve different purposes:

| Source name | Dataset | Prepared data used by the pipeline |
| --- | --- | --- |
| `onspd` | ONS Postcode Directory (ONSPD) | Postcode, local authority district (LAD), and region lookup; the charity register currently uses the LAD code |
| `utla` | ONS postcode-to-geography lookup | Postcode, upper-tier local authority (UTLA) code, and UTLA name |

The `onspd` source is distinct from ONS data generally. Its processed file,
`onspd_geography_lookup.parquet`, retains both LAD and region data. The separate
`utla` source supplies the upper-tier mapping.

> **Important:** Source arguments select configured downloads; they do not find
> the latest release on a provider's website. The Charity Commission `charity`
> and `classification` URLs point to current extracts. Other sources may use
> release-specific URLs or filenames. For example, the Companies House URL and
> filename contain `2026-09-01`, so they must be updated manually for a newer
> release. The dated local folder records the download date, not the dataset's
> release date.

### Add or change a download source

Edit the root [`config.json`](config.json), not the Python modules. Its
`downloads.sources` entries override the built-in defaults by source name and
field. New sources require `url`, `directory`, and `filename`. Update release URLs
and filenames together. For example, a source entry looks like:

```json
"company_house": {
  "url": "https://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-2026-09-01.zip",
  "directory": "data/charity_commission_register/company_house",
  "filename": "BasicCompanyDataAsOneFile-2026-09-01.zip"
}
```

`downloads.overwrite` defaults to `true`: downloads and extracted ZIP contents
are refreshed on reruns. Set it to `false` to reuse cached downloads and extracted
files. Each source directory receives a local `DDMMYYYY` download-date subfolder.
Omitted sources keep their built-in defaults; new keys add sources.

All relative data paths in JSON resolve against the repository root, regardless
of the working directory. Both scripts accept `--config path/to/config.json` for
an alternative settings file; its data paths still resolve against the repository.

The latest source data no longer includes addresses for charities that have
been removed from the register. Because these addresses are still needed for
some analyses, the legacy build target and legacy datasets are retained. The
legacy dataset is the most recent downloaded dataset that still contains this
information. It is available in the [shared legacy dataset folder](https://drive.google.com/drive/folders/1jLyCxNoDJmrcjkQQYx_yZM3h2lTKfNPy?usp=sharing).

## Build the register

Source preparation and merging live in
[`src/`](src/), the download and build commands in [`scripts/`](scripts/), and
local inputs and outputs in `data/charity_commission_register/`.

Both register variants use one script and the same preparation and merge logic.
Select the default with `build.target` in [`config.json`](config.json), currently
`"latest"`. The `build.targets.latest` and `build.targets.legacy` objects specify
the input files, prepared ONSPD output, UTLA directory or pinned CSV, and register
output basename. Add another named target by copying a target and editing its paths.

```powershell
# Use build.target from config.json
uv run python scripts/build_charity_register.py

# Override the target for this run
uv run python scripts/build_charity_register.py --target latest
uv run python scripts/build_charity_register.py --target legacy
```

Set `build.targets.latest.download_date` to a `DDMMYYYY` string (currently
`"13092026"`) to change the snapshot folder in all paths containing
`{download_date}`. Omitting the key or setting it to `null` uses today's local date.
This changes folder dates only; release-specific filenames remain explicit.
The legacy target does not need this key.

The latest target preserves the previously selected `13092026` downloads: Charity
Commission JSON and Companies House CSV, plus the retained Find That Charity CSV.
The legacy target uses the `28052025_legacy` charity, classification, Companies
House, and Find That Charity CSVs. Both targets currently share the same output
basename, preserving the existing behavior; set distinct `output_path` values
if you want separate output series.

The legacy ONSPD paths use `{today}`, expanded to the local date as `DDMMYYYY`.
Replace this token with a folder date to reuse an older download. Prepare the
geography downloads before building if needed:

```powershell
uv run python scripts/download_and_extract.py onspd utla
```

`utla_filepath: null` selects the newest dated CSV beneath `utla_directory`;
set a filepath to pin a snapshot. `onspd_source_csv_filepath: null` uses the
configured archive; set a CSV path to use a standalone postcode source instead.
The build prepares and reuses `onspd_lookup_filepath`. For a changed postcode
source, choose a new lookup output path or remove the cached lookup.

Builds use local files and do not download inputs. Download source changes do not
automatically change a target's pinned input paths: update the target explicitly
when selecting a new snapshot. `downloads.overwrite` applies only to downloads
and extraction; register outputs remain timestamped and preserve earlier runs.

## Methodology

The build retains main charity records (`linked_charity_number = 0`), includes
linked-fund classifications in the parent charity's indicators, and restricts
Find That Charity records to the Charity Commission register. Missing
classification flags become zero. Company numbers remain strings, with numeric
identifiers padded to eight characters.

The charity postcode is the first available value from Companies House,
Charity Commission, then Find That Charity. Matching ignores case and whitespace.
ONS supplies the local authority district code; the separate UTLA lookup supplies
`UTLA` and `UTLA_name`. Unmatched geography remains null. Identical UTLA mappings
are deduplicated, and conflicting postcode mappings fail validation rather than
multiply charity rows. LAD geography follows the selected ONS release, while UTLA
uses 2022 boundaries; neither reconstructs boundaries for each removal date.

Financial years begin in April. Income categories are Small below GBP 25,000,
Medium from GBP 25,000 through GBP 1,000,000, and Large above GBP 1,000,000.
Missing income leaves the size category unclassified.

Each successful build saves a new pair of files in
`data/charity_commission_register/output/`:

```text
charity_register_<YYYYMMDD_HHMMSS_microsecondsZ>.parquet
charity_register_<YYYYMMDD_HHMMSS_microsecondsZ>.run.json
```

The UTC timestamp identifies the run, and earlier outputs are preserved. The
Parquet contains the register. The JSON records run times, selected input paths
and file metadata, and output dimensions, providing a record of which local
snapshots were used.

To read the latest register:

```python
import polars as pl
from uk_charity_local_authority_analysis.charity_commission_register.build_charity_register import (
    latest_charity_register,
)

register = pl.read_parquet(latest_charity_register())
```

The same module provides `scan_charity_removals()` to aggregate removals by
local authority district, financial year, and charity size. It selects the latest
register by default or accepts a specific file path. Missing sizes are labelled
`Unknown`; records without a district code or removal year are excluded.

## Convert Parquet to CSV

Use the shared converter for files anywhere in the repository:

```powershell
uv run python -m uk_charity_local_authority_analysis.parquet_to_csv path/to/input.parquet
uv run python -m uk_charity_local_authority_analysis.parquet_to_csv path/to/input.parquet path/to/output.csv
```

The default output is beside the input with a `.csv` suffix. Parent directories
are created as needed; add `--overwrite` to replace an existing CSV. Paths are
relative to your working directory. Conversion streams through Polars; nested
columns (such as lists or structs) must be flattened before exporting to CSV.

The same function can be imported by any project or notebook:

```python
from uk_charity_local_authority_analysis.parquet_to_csv import parquet_to_csv

csv_path = parquet_to_csv("path/to/input.parquet", "path/to/output.csv")
```

## Development

Install the optional notebook dependencies with `uv sync --locked --group notebooks`.
Run the shared library tests with:

```powershell
uv run python -m unittest discover -s tests -t . -v
```

The tests in [`tests/`](tests/) cover downloads, archive extraction, source
preparation, postcode matching, and register output behaviour.
