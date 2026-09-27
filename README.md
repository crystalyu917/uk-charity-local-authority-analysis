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
some analyses, the legacy build script and legacy datasets are retained. The
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
uv sync --locked --all-groups
```

This creates the project environment and installs the dependencies defined in
`pyproject.toml`. Once the setup is complete, you can download and build the charity
register using the instructions below.


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

Default URLs and filenames are defined in
[`config.py`](src/uk_charity_local_authority_analysis/charity_commission_register/config.py).
Default local paths in
[`filepath.py`](src/uk_charity_local_authority_analysis/charity_commission_register/filepath.py)
are derived from those filenames.

For a new release or source, edit only `SOURCE_OVERRIDES` in
[`scripts/download_and_extract.py`](scripts/download_and_extract.py). Each entry
contains the command-line name and a complete source definition:

```python
SOURCE_OVERRIDES = {
    "source_name": (source_url, destination_folder, filename),
}
```

`DEFAULT_SOURCES` is built from the library defaults, then
`SOURCE_OVERRIDES` is applied. An override with an existing name replaces its
default completely; a new name adds a source. This means a maintainer can leave
`config.py` unchanged and update only the script. Always specify the complete
tuple so a dated URL and filename are changed together.

The override key becomes the command-line argument:

```powershell
uv run python scripts/download_and_extract.py source_name
```

The downloader accepts configured source names, not arbitrary URLs or local
file paths. To build from an existing local file, set the corresponding input
filepath in the relevant build script.

The latest source data no longer includes addresses for charities that have
been removed from the register. Because these addresses are still needed for
some analyses, the legacy build script and legacy datasets are retained. The
legacy dataset is the most recent downloaded dataset that still contains this
information. It is available in the [shared legacy dataset folder](https://drive.google.com/drive/folders/1jLyCxNoDJmrcjkQQYx_yZM3h2lTKfNPy?usp=sharing).

## Build the register

Source preparation and merging live in
[`src/`](src/), the download and build commands in [`scripts/`](scripts/), and
local inputs and outputs in `data/charity_commission_register/`.

### Legacy Register
Before building, supply the legacy CSV snapshots under the relative filepath:

| Source | Relative filepath |
| --- | --- |
| Charity Commission | `charity_commission/28052025_legacy/charity_commission_28052025.csv` |
| Charity Classifications | `charity_commission/28052025_legacy/charity_classification_28052025.csv` |
| Companies House | `company_house/28052025_legacy/company_house_28052025.csv` |
| Find That Charity | `find_that_charity_28052025_legacy/find_that_charity_28052025.csv` |

```powershell
uv run python scripts/build_legacy_charity_register.py
```

