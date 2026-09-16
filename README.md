# UK charity local authority analysis

This repository builds a shared England and Wales charity register by combining
Charity Commission records and classifications, Companies House information,
Find That Charity records, and ONS postcode geography. The resulting dataset
brings together charity attributes, registration and removal dates, income
categories, and local-authority codes for analysis.

The register includes a selected `charity_postcode`, a local authority district
code (`local_authority_code`), and an upper-tier local authority code and name
(`UTLA` and `UTLA_name`). Source preparation and merging live in
[`src/`](src/), the download and build commands in [`scripts/`](scripts/), and
local inputs and outputs in `data/charity_commission_register/`.

## Build the register

Run commands from the repository root with Python 3.14 or newer and `uv` installed:

```powershell
uv sync --locked
```

Source datasets and generated files are excluded from Git. Before building,
supply the following legacy CSV snapshots under
`data/charity_commission_register/`. The
[shared legacy dataset folder](https://drive.google.com/drive/folders/1jLyCxNoDJmrcjkQQYx_yZM3h2lTKfNPy?usp=sharing)
is the existing location for these inputs.

| Source | Relative filepath |
| --- | --- |
| Charity Commission | `charity_commission/28052025_legacy/charity_commission_28052025.csv` |
| Charity classifications | `charity_commission/28052025_legacy/charity_classification_28052025.csv` |
| Companies House | `company_house/28052025_legacy/company_house_28052025.csv` |
| Find That Charity | `find_that_charity_28052025_legacy/find_that_charity_28052025.csv` |

These snapshots retain address information needed for removed charities and
dissolved companies. To use other compatible files, edit the input paths in
[`scripts/build_charity_register.py`](scripts/build_charity_register.py).

Download the geography lookups, then build the register:

```powershell
uv run python scripts/download_and_extract.py ons utla
uv run python scripts/build_charity_register.py
```

Downloads are saved in folders named for the local download date (`DDMMYYYY`).
The ONS source is `ONSPD_MAY_2026.zip`; the UTLA source maps November 2023
postcodes to 2022 upper-tier authorities. Selected downloads are refreshed on
each run, and ZIPs are retained beside their extracted folders.

You can reuse existing downloads. Set `DOWNLOAD_DATE` in the build script to the
ONS folder date; UTLA selects the newest dated CSV automatically, or you can pin
one with `UTLA_LOOKUP_FILEPATH`. The build prepares and reuses
`ons/<DDMMYYYY>/ons_postcode_lookup.parquet`. To rebuild that cached lookup from
a changed archive, choose a new lookup output path or remove the cached file.

The same downloader accepts `charity`, `classification`, and `company_house`;
omitting source names downloads all five sources. Those official snapshots do
not replace or convert the legacy CSV inputs above. Download settings are in
[`scripts/download_and_extract.py`](scripts/download_and_extract.py) and
[`config.py`](src/uk_charity_local_authority_analysis/charity_commission_register/config.py).
Library path defaults are in
[`filepath.py`](src/uk_charity_local_authority_analysis/charity_commission_register/filepath.py);
explicit paths supplied by scripts or library callers take precedence. Building
uses local files and does not initiate downloads.

## Understand the register

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

## Development

Install the optional notebook dependencies with `uv sync --locked --group notebooks`.
Run the shared library tests with:

```powershell
uv run python -m unittest discover -s tests -t . -v
```

The tests in [`tests/`](tests/) cover downloads, archive extraction, source
preparation, postcode matching, and register output behaviour.
