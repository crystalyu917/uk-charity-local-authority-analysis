"""Match the project charity register to CCOD and registered leases."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time

import polars as pl

from charity_lease.pipeline.lease_terms import add_lease_terms
from charity_lease.data import DATA_DIR, latest_register, latest_property_input, local_path, validate_charity_numbers
from charity_lease.pipeline.core import (
    load_properties,
    match_properties, merge_matches, prepare_charities,
    incomplete_tail_offset, complete_csv_prefix, active_charities, deduplicate_charities,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charity-input", type=Path, help="Defaults to latest local charity_register Parquet.")
    parser.add_argument("--ccod-input", type=Path, help="Defaults to newest CCOD_FULL_YYYY_MM.csv in datasets/.")
    parser.add_argument("--leases-input", type=Path, help="Defaults to newest LEASES_FULL_YYYY_MM.csv in datasets/.")
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR / "output")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD for lease estimates.")
    parser.add_argument("--exact-only", action="store_true", help="Only compare identical normalized address/postcode keys.")
    parser.add_argument("--min-score", type=float, default=72.0, help="Minimum candidate score, 0-100.")
    parser.add_argument("--format", choices=("parquet", "csv"), default="parquet")
    parser.add_argument("--allow-incomplete-leases", dest="allow_incomplete_leases",
                              action="store_true", default=False,
                              help="Explicitly allow complete records from a truncated leases CSV; mark the output incomplete.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 <= args.min_score <= 100:
        raise ValueError("--min-score must be between 0 and 100")
    inputs = {
        "charity": local_path(args.charity_input) if args.charity_input else latest_register(),
        "ccod": local_path(args.ccod_input) if args.ccod_input else latest_property_input("ccod"),
        "lease": local_path(args.leases_input) if args.leases_input else latest_property_input("lease"),
    }
    for path in inputs.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    for kind, path in inputs.items():
        print(f"Using {kind} input: {path}", flush=True)
    output_dir = local_path(args.output_dir)
    lease_offset = incomplete_tail_offset(inputs["lease"])
    if lease_offset is not None and not args.allow_incomplete_leases:
        raise ValueError("The leases CSV ends inside a quoted field. Supply a complete file, "
                         "or pass --allow-incomplete-leases to use its complete records.")
    if lease_offset is not None:
        print("Leases source is incomplete: excluding the unfinished final record; "
              "lease_source_incomplete will be True.", flush=True)
    started = datetime.now(timezone.utc)
    run_dir = output_dir / started.strftime("%Y%m%d_%H%M%S_%fZ")
    register = active_charities(pl.read_parquet(inputs["charity"]))
    entities = prepare_charities(register)
    print(f"Loaded {register.height:,} charity rows; "
          f"{entities.filter(pl.col('address_match_key').is_not_null())['_source_row'].n_unique():,} usable addresses.", flush=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    with TemporaryDirectory(prefix=".building-", dir=output_dir) as stage:
        staging = Path(stage)
        for kind in ("ccod", "lease"):
            tick = time.monotonic()
            print(f"Reading {kind} property rows for charity postcodes...", flush=True)
            with complete_csv_prefix(inputs[kind], lease_offset if kind == "lease" else None, staging) as source:
                properties = load_properties(source, kind, entities)
            print(f"Retained {properties.height:,} {kind} property rows.", flush=True)
            best = match_properties(
                entities, properties, kind, fuzzy=not args.exact_only, min_score=args.min_score,
            )
            parts.append(best)
            review = best[f"{kind}_needs_manual_review"].sum()
            print(f"{kind}: {best.height:,} matches ({review:,} for review) "
                  f"in {time.monotonic() - tick:.1f}s.", flush=True)
        result = deduplicate_charities(add_lease_terms(merge_matches(register, entities, parts), args.as_of))
        validate_charity_numbers(result, unique=True)
        result = result.with_columns(pl.lit(lease_offset is not None).alias("lease_source_incomplete"))
        # Long-running matching may outlive an external cleanup of temporary folders.
        staging.mkdir(parents=True, exist_ok=True)
        if args.format == "csv":
            result.write_csv(staging / "charity_register_with_property.csv")
        else:
            result.write_parquet(staging / "charity_register_with_property.parquet")
        # Publish the completed file without replacing an earlier run. Linking
        # the file avoids Windows locks on temporary input directories.
        run_dir.mkdir(exist_ok=False)
        name = f"charity_register_with_property.{args.format}"
        try:
            os.link(staging / name, run_dir / name)
        except OSError:
            run_dir.rmdir()
            raise
    print(f"Saved {result.height:,} rows to {run_dir}", flush=True)


if __name__ == "__main__":
    main()
