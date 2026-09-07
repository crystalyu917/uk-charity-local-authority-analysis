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
under `data/`, and common dataset formats are excluded from Git.

## Datasets

Legacy datasets can be found here:
https://drive.google.com/drive/folders/1jLyCxNoDJmrcjkQQYx_yZM3h2lTKfNPy?usp=sharing


## Module guides

| Module              | Guide                                                                                                                               | Default data directory      |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| Core                | [Inputs, charity register builds, ONS lookup, and run records](src/uk_charity_local_authority_analysis/core/README.md)              | `data/core/`                |
| Council asset sales | [Receipt inputs, charity-removals panel, and interpretation](src/uk_charity_local_authority_analysis/council_asset_sales/README.md) | `data/council_asset_sales/` |

Each module has its own `config.py`. Configure council analysis in its folder;
core configuration is for core data preparation. If starting from raw charity
sources, build core outputs first, then follow the council guide to select them.

## Notebooks

Exploratory notebooks live under `notebooks/`, grouped by module, and read from
that module's prepared outputs (for example `data/council_asset_sales/raw/`
and `data/council_asset_sales/output/`). Notebook dependencies (Jupyter,
pandas, matplotlib, statsmodels, seaborn, pyarrow) are kept out of the base
install and live in the `notebooks` dependency group:

```powershell
uv sync --group notebooks
```

Launch Jupyter from the repository root with `uv run jupyter lab` (or
`jupyter notebook`), then open a notebook under `notebooks/`. Build the
relevant module's outputs first, and restart the kernel after editing a
module's `config.py`.

## Tests

Tests live in `tests/` subfolders of the modules they cover. Run the full suite:

```powershell
uv run python -m unittest discover -s src -v
```

Each module guide also includes a command for running only that module's tests.
