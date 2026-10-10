"""Shared cohorts and summaries used by the maintained analysis notebook."""

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from .data import boolean_flag, latest_output, local_path, read_output, validate_charity_numbers
from .pipeline.core import active_charities
from .pipeline.lease_terms import TERM_SCHEMA, eligible_registered_lease, select_tenure


MATCH_ORDER = ["Both sources", "Registered Leases only", "CCOD only", "No Land Registry match"]
SIZE_ORDER = ["Small", "Medium", "Large", "Unknown size"]
TERM_LABELS = ["Under 5 years", "5 to <10 years", "10 to <25 years", "25 to <50 years",
               "50 to <100 years", "100 to <125 years", "125+ years"]
TERM_BINS = [0, 5, 10, 25, 50, 100, 125, np.inf]
COUNTRY_PREFIXES = {"E": "England", "W": "Wales", "S": "Scotland", "N": "Northern Ireland",
                    "L": "Channel Islands", "M": "Isle of Man"}
BOOL_COLUMNS = ["charity_has_land", "registered_lease_matched", "ccod_matched", "review",
                "ccod_needs_manual_review", "lease_needs_manual_review",
                "lease_source_incomplete", "charity_is_freeholder"]


def load_analysis_data(path: str | Path | None = None) -> tuple[Path, pd.DataFrame]:
    """Validate current output decisions, then derive descriptive columns once."""
    path = local_path(path) if path is not None else latest_output()
    frame = read_output(path)
    required = set(BOOL_COLUMNS) | set(TERM_SCHEMA) | {
        "registered_charity_number", "charity_name", "lease_status", "ccod_tenure",
        "lease_term_as_of_date", "size_category", "local_authority_code", "UTLA", "UTLA_name",
        *[f"ccod_proprietor_name_{i}" for i in range(1, 5)],
    }
    if missing := required - set(frame.columns):
        raise ValueError(f"Output lacks current analysis columns: {sorted(missing)}. "
                         "Run charity-lease-match; historical suppressed-source outputs cannot "
                         "reconstruct both sources.")
    if frame.is_empty():
        raise ValueError("The selected output contains no charities")
    validate_charity_numbers(frame, unique=True)
    if active_charities(frame).height != frame.height:
        raise ValueError("Expected an output without charity removal dates")
    frame = frame.with_columns([boolean_flag(c).alias(c) for c in BOOL_COLUMNS])
    for name in set(BOOL_COLUMNS) - {"charity_has_land"}:
        if frame[name].null_count():
            raise ValueError(f"Missing or invalid values in {name}")
    # Validate saved tenure against the same function used during matching.
    selected = select_tenure(frame)
    for name in ("lease_status", "charity_is_freeholder"):
        if not frame[name].equals(selected[name]):
            raise ValueError(f"Saved {name} differs from current pipeline rules; rerun charity-lease-match")
    expected_review = frame["ccod_needs_manual_review"] | frame["lease_needs_manual_review"]
    if not frame["review"].equals(expected_review):
        raise ValueError("Combined review flag must include both sources")
    freeholders = frame.filter(pl.col("charity_is_freeholder"))
    if any(freeholders[c].null_count() != freeholders.height for c in TERM_SCHEMA if c != "lease_term_parse_status"):
        raise ValueError("Charity freeholders must have suppressed lease estimates")
    frame = frame.with_columns(eligible_registered_lease().alias("eligible_registered_leases"))
    data = frame.to_pandas()
    data["matched_registered_leases"] = data["registered_lease_matched"].astype(bool)
    data["matched_ccod"] = data["ccod_matched"].astype(bool)
    data["matched_both"] = data["matched_registered_leases"] & data["matched_ccod"]
    data["any_land_registry_match"] = data["matched_registered_leases"] | data["matched_ccod"]
    data["land_registry_match"] = np.select(
        [data["matched_both"], data["matched_registered_leases"], data["matched_ccod"]],
        MATCH_ORDER[:3], default=MATCH_ORDER[3],
    )
    data["registry_tenure"] = data["lease_status"].map({"freehold": "Freehold", "leasehold": "Lease"}).fillna("No data")
    data["charity_has_land_label"] = data["charity_has_land"].map({True: "True", False: "False"}).fillna("Unknown")
    data["reports_land"] = data["charity_has_land"].fillna(False).astype(bool)
    data["lease_term_years_num"] = pd.to_numeric(data["lease_term_years"], errors="coerce")
    data["lease_term_years_num"] = data["lease_term_years_num"].where(data["lease_term_years_num"] > 0)
    data["charity_size"] = data["size_category"].where(data["size_category"].isin(SIZE_ORDER[:3]), SIZE_ORDER[3])
    data["term_band"] = pd.cut(data["lease_term_years_num"], bins=TERM_BINS, labels=TERM_LABELS,
                                right=False).astype("string").fillna("Unknown")
    code = data["local_authority_code"].astype("string").str.strip().replace("", pd.NA)
    data["local_authority"] = code.fillna("Unknown")
    data["country"] = code.str[0].map(COUNTRY_PREFIXES).fillna("Unknown")
    utla = data["UTLA"].astype("string").str.strip().replace("", pd.NA)
    name = data["UTLA_name"].astype("string").str.strip().replace("", pd.NA)
    data["upper_tier_authority"] = (name.fillna(utla) + " (" + utla + ")").fillna("Unknown")
    return path, data


def geographic_summary(data: pd.DataFrame, geography: str) -> pd.DataFrame:
    """Separate raw source coverage from the eligible known-duration cohort."""
    def summarise(group):
        leases = group[group["eligible_registered_leases"]]
        known = leases["lease_term_years_num"].dropna()
        land = group[group["reports_land"]]
        return pd.Series({
            "charities": len(group),
            "unknown_land_response": group["charity_has_land"].isna().sum(),
            "lease_matches": group["matched_registered_leases"].sum(),
            "eligible_lease_matches": len(leases),
            "known_lease_terms": len(known),
            "median_lease_term_years": known.median(),
            "leases_20_years_or_less": known.le(20).sum(),
            "leases_over_20_years": known.gt(20).sum(),
            "leases_over_20_years_pct": 100 * known.gt(20).mean() if len(known) else np.nan,
            "land_reporting_charities": len(land),
            "land_reporting_matched_to_leases_pct": 100 * land["matched_registered_leases"].mean() if len(land) else np.nan,
        })
    result = data.groupby(geography, dropna=False).apply(summarise, include_groups=False).reset_index()
    counts = ["charities", "unknown_land_response", "lease_matches", "eligible_lease_matches",
              "known_lease_terms", "leases_20_years_or_less", "leases_over_20_years", "land_reporting_charities"]
    result[counts] = result[counts].astype(int)
    return result.sort_values(["lease_matches", geography], ascending=[False, True]).reset_index(drop=True)
