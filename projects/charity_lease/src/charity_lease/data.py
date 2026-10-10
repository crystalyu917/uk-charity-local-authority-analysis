"""Project paths, completed-run discovery and shared data validation."""

from pathlib import Path
import re

import polars as pl

from .pipeline.address_cleaning import MISSING_MARKERS


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "datasets"
RUN_PATTERN = re.compile(r"\d{8}_\d{6}_\d{6}Z")


def local_path(value: str | Path) -> Path:
    """Resolve every data path inside this project."""
    path = Path(value)
    path = (path if path.is_absolute() else PROJECT_DIR / path).resolve()
    if not path.is_relative_to(PROJECT_DIR):
        raise ValueError(f"Path must be inside {PROJECT_DIR}: {path}")
    return path


def completed_runs(output_dir: str | Path = DATA_DIR / "output") -> list[Path]:
    """Return completed runs in timestamp order, preferring Parquet per run."""
    folder = local_path(output_dir)
    runs = {}
    for extension in ("csv", "parquet"):
        for path in folder.glob(f"*/charity_register_with_property.{extension}"):
            if RUN_PATTERN.fullmatch(path.parent.name):
                runs[path.parent.name] = local_path(path)
    return [runs[key] for key in sorted(runs)]


def latest_register(folder: str | Path = DATA_DIR / "charity_register_inputs") -> Path:
    """Select a register by its filename timestamp, with a plain-name fallback."""
    folder = local_path(folder)
    pattern = re.compile(r"charity_register_\d{8}_\d{6}_\d{6}Z\.parquet")
    candidates = [p for p in folder.glob("*.parquet") if p.is_file() and pattern.fullmatch(p.name)]
    if candidates:
        return local_path(max(candidates, key=lambda p: p.name))
    fallback = folder / "charity_register.parquet"
    if fallback.is_file():
        return local_path(fallback)
    raise FileNotFoundError(f"Supply a charity_register Parquet in {folder}, or pass --charity-input")


def latest_property_input(kind: str, folder: str | Path = DATA_DIR) -> Path:
    """Select a property's source month from its standard filename."""
    prefixes = {"ccod": "CCOD", "lease": "LEASES"}
    if kind not in prefixes:
        raise ValueError(f"Unknown property source: {kind}")
    folder = local_path(folder)
    prefix = prefixes[kind]
    pattern = re.compile(rf"{prefix}_FULL_[1-9]\d{{3}}_(?:0[1-9]|1[0-2])\.csv")
    candidates = [p for p in folder.glob(f"{prefix}_FULL_*.csv")
                  if p.is_file() and pattern.fullmatch(p.name)]
    if not candidates:
        option = "--ccod-input" if kind == "ccod" else "--leases-input"
        raise FileNotFoundError(f"No {prefix}_FULL_YYYY_MM.csv in {folder}; supply a file or pass {option}")
    return local_path(max(candidates, key=lambda p: p.name))


def latest_output() -> Path:
    runs = completed_runs()
    if not runs:
        raise FileNotFoundError("No completed output; run charity-lease-match first.")
    return runs[-1]


def read_output(path: str | Path, columns: list[str] | None = None) -> pl.DataFrame:
    path = local_path(path)
    if path.suffix == ".parquet":
        return pl.read_parquet(path, columns=columns)
    if path.suffix == ".csv":
        return pl.read_csv(path, columns=columns, infer_schema=False)
    raise ValueError("Completed outputs must be Parquet or CSV")


def boolean_flag(name: str) -> pl.Expr:
    """Interpret native booleans and their CSV string representations equally."""
    return pl.col(name).cast(pl.String).str.strip_chars().str.to_lowercase().replace_strict(
        {"true": True, "false": False}, default=None, return_dtype=pl.Boolean,
    )


def validate_charity_numbers(frame: pl.DataFrame, *, unique: bool = False) -> None:
    """Require usable identifiers; duplicates are permitted before deduplication."""
    name = "registered_charity_number"
    if name not in frame.columns:
        raise ValueError(f"Missing {name}")
    numbers = frame[name].cast(pl.String).str.strip_chars()
    if numbers.is_null().any() or numbers.str.to_uppercase().is_in(sorted(MISSING_MARKERS)).any():
        raise ValueError("Registered charity numbers must be nonmissing")
    if unique and numbers.n_unique() != frame.height:
        raise ValueError("Expected one unique registered charity number per output row")
