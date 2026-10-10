"""Estimate lease expiry and select tenure with a charity freeholder exception."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import re

import polars as pl

from .address_cleaning import clean_owner_name
from .address_matching import owner_ratio
from ..data import boolean_flag


TERM_SCHEMA = {
    "lease_term_years": pl.Float64,
    "lease_start_date_parsed": pl.Date,
    "lease_expiry_date": pl.Date,
    "lease_years_remaining": pl.Float64,
    "lease_term_parse_status": pl.String,
}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = re.sub(r"(\d)(ST|ND|RD|TH)\b", r"\1", str(value).upper().strip())
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_lease_term_years(term: str | None) -> float | None:
    """Extract a numeric year duration, including fractions."""
    if not term:
        return None
    for unit in (r"YEARS?", r"YRS?"):
        match = re.search(r"(\d+(?:\.\d+)?)\s*" + unit, str(term).upper())
        if match:
            return float(match.group(1))
    return None


def calculate_lease_expiry(start: date | None, years: float | None) -> date | None:
    if start is None or not years:
        return None
    try:
        full_years = int(years)
        year = start.year + full_years
        return date(year, start.month, min(start.day, calendar.monthrange(year, start.month)[1])) + timedelta(
            days=int((years - full_years) * 365.25)
        )
    except (ValueError, OverflowError):
        return None


def parse_term(term: str | None, deed_date: str | None, as_of: date) -> dict:
    """Estimate duration from Date of Lease rather than the date written in Term."""
    years = parse_lease_term_years(term)
    start = parse_date(deed_date)
    expiry = calculate_lease_expiry(start, years)
    return {
        "lease_term_years": years,
        "lease_start_date_parsed": start,
        "lease_expiry_date": expiry,
        "lease_years_remaining": max(0.0, (expiry - as_of).days / 365.25) if expiry else None,
        "lease_term_parse_status": "estimated_from_deed_date" if expiry else "missing" if not term else "unparsed",
    }


def select_tenure(frame: pl.DataFrame) -> pl.DataFrame:
    """Select tenure, giving a fuzzy-matched charity freeholder priority.

    Preserve both sources as evidence, including CCOD company numbers. Missing
    names never match; use the existing owner scorer without its candidate-name
    fallback. The selected CCOD property's four proprietors are all considered.
    """
    def column(name: str) -> pl.Expr:
        return pl.col(name) if name in frame.columns else pl.lit(None, dtype=pl.String)

    evidence = []
    names = ["charity_name", *[f"ccod_proprietor_name_{i}" for i in range(1, 5)]]
    for charity, *owners in frame.with_columns(
        [column(c).alias(c) for c in names]
    ).select(names).iter_rows():
        charity = clean_owner_name(charity)
        scored = [(owner_ratio(charity, cleaned), raw) for raw in owners
                  if charity and (cleaned := clean_owner_name(raw))]
        score, name = max(scored, key=lambda item: item[0]) if scored else (None, None)
        evidence.append((name, score))
    frame = frame.with_columns(pl.DataFrame(evidence, orient="row", schema={
        "ccod_best_matching_proprietor_name": pl.String,
        "ccod_proprietor_name_match_score": pl.Float64,
    }).get_columns())
    ccod = boolean_flag("ccod_matched").fill_null(False) if "ccod_matched" in frame.columns else pl.lit(False)
    lease = boolean_flag("registered_lease_matched").fill_null(False)
    tenure = column("ccod_tenure").cast(pl.String).str.strip_chars().str.to_lowercase()
    freeholder = (ccod & (tenure == "freehold") &
                  (pl.col("ccod_proprietor_name_match_score") >= 92)).fill_null(False)
    return frame.with_columns(
        freeholder.alias("charity_is_freeholder"),
        pl.when(freeholder).then(pl.lit("freehold"))
        .when(lease).then(pl.lit("leasehold"))
        .when(ccod).then(tenure).otherwise(None).alias("lease_status"),
    )


def eligible_registered_lease() -> pl.Expr:
    """The shared cohort for lease estimates and their descriptive summaries."""
    return (boolean_flag("registered_lease_matched").fill_null(False)
            & (pl.col("lease_status") == "leasehold").fill_null(False))


def add_lease_terms(frame: pl.DataFrame, as_of: date) -> pl.DataFrame:
    required = {"lease_term", "lease_date_of_lease", "registered_lease_matched"}
    if missing := required - set(frame.columns):
        raise ValueError(f"Missing lease columns: {sorted(missing)}")
    overlap = (set(TERM_SCHEMA) | {"lease_term_as_of_date"}) & set(frame.columns)
    if overlap:
        raise ValueError(f"Lease estimates already exist: {sorted(overlap)}")
    frame = select_tenure(frame)
    eligibility = frame.select(eligible_registered_lease().alias("eligible"))["eligible"]
    parsed = [
        parse_term(term, deed, as_of) if eligible
        else {**dict.fromkeys(TERM_SCHEMA), "lease_term_parse_status": "unmatched"}
        for (term, deed), eligible in zip(
            frame.select("lease_term", "lease_date_of_lease").iter_rows(), eligibility, strict=True,
        )
    ]
    return frame.hstack(pl.DataFrame(parsed, schema=TERM_SCHEMA)).with_columns(
        pl.lit(as_of).alias("lease_term_as_of_date")
    )

