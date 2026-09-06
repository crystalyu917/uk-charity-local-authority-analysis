
# UK charity local authority analysis

Run these commands in PowerShell from the repository root. Install `uv` first;
`uv run` installs the project's Python 3.14 environment and dependencies as needed.

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

To change releases, update the item ID and filename in
[`endpoint.py`](src/uk_charity_local_authority_analysis/core/datasets/ons_postcode_lookup/endpoint.py).
Remove the existing Parquet before building the new release. An optional
standalone `onspd_may_2026_uk.csv` directly inside `data\core\ons\raw` is used
by `build` in preference to downloading; this fallback produces codes with null
geography names.

Run the offline regression checks with:

```powershell
uv run python -m unittest discover -s tests -v
```
