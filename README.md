# UK charity local authority analysis

Run these commands in PowerShell from the repository root. Install `uv` first;
`uv run` installs the project's Python 3.14 environment and dependencies as needed.

Start by choosing your inputs in
[`core/config.py`](src/uk_charity_local_authority_analysis/core/config.py).
The examples below use the default paths; your configured paths take precedence.

## ONS download

Download the configured ONS Postcode Directory ZIP into `data\core\ons\raw`:

```powershell
uv run python -m uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup download
```

The current endpoint is the [May 2026 ONS Postcode Directory](https://geoportal.statistics.gov.uk/datasets/6fff67d204fd4f339591ed667a6e3642/about).
The ZIP is approximately 247 MB. Paths are resolved from the repository location.

Download and extract only the combined postcode CSV and the LAD and region lookups:

```powershell
uv run python -m uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup extract
```

Download, extract, and build `data\core\ons\raw\ons_postcode_lookup.parquet`:

```powershell
uv run python -m uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup build
```

Omitting the action also runs `build`. The Parquet contains `pcd`, `lad`
(code and name), and `region` (code and name). Source files stay under
`data\core\ons\raw\ONSPD_MAY_2026`.

Existing downloads and completed Parquet outputs are reused. Extracted files
are reused when their sizes match the ZIP metadata. To refresh an existing
download, remove its ZIP first; to rebuild an existing Parquet, remove that
Parquet first. Interrupted downloads use temporary files and do not replace
the final ZIP.

## Data configuration

Edit [`core/config.py`](src/uk_charity_local_authority_analysis/core/config.py)
for all source directories, input filenames, output paths, and the ONS download
endpoint. Save the file and rerun the command (restart Python in a notebook).
You do not need to edit `charity.py`, `constants.py`, or `endpoint.py`.

| What to change | Settings in `core/config.py` |
| --- | --- |
| Charity Commission input folder | `CHARITY_COMMISSION_DIR` |
| Charity and classification CSVs | `CHARITY`, `CHARITY_CLASSIFICATION` |
| Companies House input | `COMPANY_HOUSE_DIR`, `COMPANY_HOUSE` |
| Find That Charity input | `FIND_THAT_CHARITY_DIR`, `FIND_THAT_CHARITY` |
| ONS download URL | `ONS_POSTCODE_LOOKUP_ITEM_ID`, `ONS_POSTCODE_LOOKUP_URL` |
| ONS ZIP location | `ONS_RAW_DIR`, `ONS_POSTCODE_LOOKUP_FILENAME` |
| Optional local ONS CSV | `ONS_SOURCE_CSV` |
| Generated Parquet files | `ONS_OUTPUT_PATH`, `CHARITY_OUTPUT_PATH` |

`legacy_raw` is simply the default folder name, not a required data mode.
Set each directory and filename to the data you want to use.

For example, use a non-legacy Charity Commission directory:

```python
CHARITY_COMMISSION_DIR = DEFAULT_DATA_DIR / "charity_commission" / "raw"
CHARITY = CHARITY_COMMISSION_DIR / "charity_commission_latest.csv"
CHARITY_CLASSIFICATION = CHARITY_COMMISSION_DIR / "charity_classification_latest.csv"
```

Or use an external directory:

```python
COMPANY_HOUSE_DIR = Path("D:/datasets/companies")
COMPANY_HOUSE = COMPANY_HOUSE_DIR / "companies.csv"
```

Relative paths should be anchored to `PROJECT_ROOT`; absolute paths work too.
The selected CSVs must have the columns expected by the existing pipeline.

In the same file, set `ONS_POSTCODE_LOOKUP_ITEM_ID` (or replace
`ONS_POSTCODE_LOOKUP_URL` with a direct download URL),
`ONS_POSTCODE_LOOKUP_FILENAME`, and `ONS_RAW_DIR`. For a different release, also
change `ONS_OUTPUT_PATH` or remove the old Parquet to avoid reusing its cache.
For example, the default ONS settings in that file are:

```python
ONS_RAW_DIR = DEFAULT_DATA_DIR / "ons" / "raw"
ONS_POSTCODE_LOOKUP_ITEM_ID = "6fff67d204fd4f339591ed667a6e3642"
ONS_POSTCODE_LOOKUP_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ONS_POSTCODE_LOOKUP_ITEM_ID}/data"
)
ONS_POSTCODE_LOOKUP_FILENAME = "ONSPD_MAY_2026.zip"
ONS_OUTPUT_PATH = ONS_RAW_DIR / "ons_postcode_lookup.parquet"
```

Keep the item ID and ZIP filename aligned with your chosen release. A replacement
URL must serve a compatible ONS ZIP archive, not a dataset landing page.
ONS is currently the only implemented downloader; the other sources use local CSVs.

Set `ONS_SOURCE_CSV` to a CSV path to build from that file, or leave it as `None`
to use the official ZIP and its LAD/region name lookups. A configured CSV must
exist and rebuilds the Parquet on every build, with null geography names.
An explicitly supplied `source_csv` function argument overrides the configuration.

```python
ONS_SOURCE_CSV = Path("D:/datasets/ons/postcodes.csv")
```

This setting affects `build`; `download` and `extract` still use the configured
ZIP endpoint. After changing configuration, run the same build commands shown
below; no extra command-line options are needed.

## Integrated charity register

Build the register from this repository's local snapshots:

```powershell
uv run python -m uk_charity_local_authority_analysis.core
```

Default output: `data\core\output\charity_register.parquet` (`CHARITY_OUTPUT_PATH`). Each run rebuilds this
output, replacing it only after the new Parquet is complete. The default input paths are:

- `data\core\charity_commission\legacy_raw\charity_commission_28052025.csv`
- `data\core\charity_commission\legacy_raw\charity_classification_28052025.csv`
- `data\core\company_house\legacy_raw\company_house_28052025.csv`
- `data\core\find_that_charity\legacy_raw\find_that_charity_28052025.csv`

Supply the selected CSVs locally; the pipeline does not download them.
The ONS Parquet is built automatically if missing. Input locations are configured
in [`core/config.py`](src/uk_charity_local_authority_analysis/core/config.py).

The register covers England and Wales Charity Commission records. It uses main
charity records (`linked_charity_number = 0`), restricts Find That Charity to
`ccew`, and validates joins to prevent duplicate lookup records multiplying rows.
Company identifiers remain strings with numeric identifiers padded to eight
characters. Companies House is scanned for matching company numbers before
loading the relevant records. Postcode precedence is Companies House, Charity
Commission, then Find That Charity; postcodes without an ONS match retain a null
local authority code. Classification flags include linked-fund classifications
under their parent charity and are zero when absent.

The default configuration selects May 2025 snapshots and May 2026 ONS
geographies. This is a snapshot analysis, not a historical geography reconstruction.
Financial years start in April; income bands are Small below 25,000, Medium from
25,000 through 1,000,000, and Large above 1,000,000. Missing income is unclassified.

To aggregate removals by local authority, financial year, and size:

```python
from uk_charity_local_authority_analysis.core.charity import scan_charity_removals

removals = scan_charity_removals().collect()
```

Rows without a local authority or removal year are excluded from this aggregation.

## Checks

Run the offline regression checks with:

```powershell
uv run python -m unittest discover -s tests -v
```
