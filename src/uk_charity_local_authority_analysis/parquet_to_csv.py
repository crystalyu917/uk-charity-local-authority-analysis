"""Convert a Parquet file to CSV using the shared Polars dependency."""

import argparse
from pathlib import Path

import polars as pl


def parquet_to_csv(
    source: str | Path,
    output: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Stream Parquet rows to CSV and return the output path.

    By default, replace the source's suffix with ``.csv``. Relative paths
    resolve against the caller's working directory. Existing outputs require
    ``overwrite=True``. Nested Parquet columns are unsupported by CSV.
    """
    source = Path(source)
    output = Path(output) if output is not None else source.with_suffix(".csv")
    if not source.is_file():
        raise FileNotFoundError(f"Parquet file not found: {source}")
    if source.resolve() == output.resolve():
        raise ValueError("Input and output paths must be different.")
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output}; use overwrite=True.")
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.scan_parquet(source).sink_csv(output, engine="streaming")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Input Parquet file.")
    parser.add_argument("output", nargs="?", type=Path, help="Output CSV path (default: beside input).")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing CSV.")
    args = parser.parse_args()
    try:
        output = parquet_to_csv(args.source, args.output, overwrite=args.overwrite)
    except (OSError, ValueError, pl.exceptions.PolarsError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
