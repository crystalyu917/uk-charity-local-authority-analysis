"""Project-local property matching using Polars and the Python standard library."""

from __future__ import annotations

from contextlib import contextmanager
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl

from .address_cleaning import (
    clean_owner_name, extract_postcode, format_postcode, make_address_match_key,
    split_address_sections_by_postcode, split_numbers, standardise_address_words, squish,
    MISSING_MARKERS,
)
from .address_matching import MatchConfig, build_postcode_candidates, rank_candidates, select_best_matches
from ..data import local_path, validate_charity_numbers

POSTCODE_PATTERN = r"\b(?:GIR\s*0AA|[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2})\b"
PROPERTY_FIELDS = {
    "ccod": {
        "Title Number": "title_number", "Tenure": "tenure",
        "Property Address": "full_address", "District": "district",
        "County": "county", "Region": "region", "Postcode": "postcode",
        "Multiple Address Indicator": "multiple_address_indicator",
        "Price Paid": "price_paid", "Date Proprietor Added": "date_proprietor_added",
        "Additional Proprietor Indicator": "additional_proprietor_indicator",
        **{f"Proprietor Name ({i})": f"proprietor_name_{i}" for i in range(1, 5)},
        **{f"Company Registration No. ({i})": f"company_registration_no_{i}" for i in range(1, 5)},
        **{f"Proprietorship Category ({i})": f"proprietorship_category_{i}" for i in range(1, 5)},
        **{f"Proprietor ({i}) Address ({j})": f"proprietor_{i}_address_{j}"
           for i in range(1, 5) for j in range(1, 4)},
    },
    "lease": {
        "Unique Identifier": "unique_identifier", "Tenure": "tenure",
        "Register Property Description": "register_property_description",
        "Associated Property Description": "associated_property_description",
        "County": "county", "Region": "region",
        "Associated Property Description ID": "associated_property_description_id",
        "OS UPRN": "uprn", "Price Paid": "price_paid", "Reg Order": "reg_order",
        "Date of Lease": "date_of_lease", "Term": "term",
        "Alienation Clause Indicator": "alienation_clause_indicator",
    },
}


def incomplete_tail_offset(path: Path) -> int | None:
    """Validate logical records, including quoted newlines, and locate a truncated tail."""
    # csv.reader consumes physical lines on demand; track bytes without text tell().
    offset = 0
    def lines(stream):
        nonlocal offset
        for line in stream:
            offset += len(line)
            yield line.decode("utf-8-sig" if offset == len(line) else "utf-8")

    with path.open("rb") as stream:
        reader = csv.reader(lines(stream), strict=True)
        while True:
            start = offset
            try:
                next(reader)
            except StopIteration:
                return None
            except csv.Error as error:
                if "unexpected end of data" in str(error):
                    return start
                raise ValueError(f"Malformed CSV record at byte {start} in {path}: {error}") from error


@contextmanager
def complete_csv_prefix(path: Path, offset: int | None, staging: Path):
    """Make a temporary copy of complete records; never alter the raw input."""
    if offset is None:
        yield path
        return
    with TemporaryDirectory(prefix=".input-", dir=staging) as folder:
        complete = Path(folder) / path.name
        with path.open("rb") as source, complete.open("wb") as output:
            remaining = offset
            while remaining:
                block = source.read(min(8 * 1024 * 1024, remaining))
                if not block:
                    raise ValueError("Source changed while copying complete CSV records")
                output.write(block)
                remaining -= len(block)
        yield complete


def text(column: str) -> pl.Expr:
    value = pl.col(column).cast(pl.String).str.strip_chars()
    return pl.when(value.str.to_uppercase().is_in(sorted(MISSING_MARKERS))).then(None).otherwise(value)


def postcode(expr: pl.Expr) -> pl.Expr:
    return expr.str.to_uppercase().str.replace_all(r"\s+", "").replace("", None)


MATCH_COLUMNS = ["postcode_clean", "address_expanded", "owner_clean",
                 "address_match_key", "owner_address_match_key"]


def expand_addresses(frame: pl.DataFrame, address_col: str, postcode_col: str | None,
                     owner_col: str | None) -> pl.DataFrame:
    """Expand postcode sections and address numbers without copying wide rows."""
    variants = []
    selected = frame.select(pl.col(address_col).alias("address"),
        pl.col(postcode_col).alias("postcode") if postcode_col else pl.lit(None).alias("postcode"),
        pl.col(owner_col).alias("owner") if owner_col else pl.lit(None).alias("owner"))
    for row_id, (raw, supplied, owner) in enumerate(selected.iter_rows()):
        owner = clean_owner_name(owner)
        sections = split_address_sections_by_postcode(raw)
        if len(sections) <= 1:
            sections = [(raw, extract_postcode(supplied) or format_postcode(supplied) or extract_postcode(raw))]
        for section, pc in sections:
            clean = standardise_address_words(section, pc)
            for expanded in split_numbers(clean) or [None]:
                key = make_address_match_key(expanded, pc)
                variants.append((row_id, pc, expanded, owner, key,
                                 f"{owner} | {key}" if owner and key else None))
    schema = {"_expand_row": pl.UInt32, **{c: pl.String for c in MATCH_COLUMNS}}
    expanded = pl.DataFrame(variants, schema=schema, orient="row")
    return frame.with_row_index("_expand_row").join(expanded, on="_expand_row", how="left",
        maintain_order="left").drop("_expand_row")


def prepare_charities(register: pl.DataFrame) -> pl.DataFrame:
    """Prefer the embedded registered address, then the contact address."""
    required = {"charity_name", "registered_charity_number"}
    if missing := required - set(register.columns):
        raise ValueError(f"Register is missing columns: {sorted(missing)}")
    validate_charity_numbers(register)
    if "_source_row" in register.columns:
        raise ValueError("Input contains reserved column _source_row")

    def parts(columns: list[str]) -> pl.Expr:
        present = [text(c).map_elements(squish, return_dtype=pl.String) for c in columns if c in register.columns]
        return (pl.concat_str(present, separator=" ", ignore_nulls=True)
                .str.replace_all(r"\s+", " ").str.strip_chars().replace("", None)
                if present else pl.lit(None, dtype=pl.String))

    def first(columns: list[str]) -> pl.Expr:
        present = [text(c).map_elements(squish, return_dtype=pl.String) for c in columns if c in register.columns]
        return pl.coalesce(present) if present else pl.lit(None, dtype=pl.String)

    company = parts(["RegAddress.AddressLine1", "RegAddress.AddressLine2",
                     "RegAddress.PostTown", "RegAddress.County", "RegAddress.Country"])
    registered = parts([
        *[f"{prefix}{i}" for prefix in ("charity_registered_address", "registered_address",
          "charity_register_address", "register_address") for i in range(1, 6)],
        "charity_registered_address", "registered_address", "charity_register_address", "register_address",
    ])
    contact = parts([*[f"{prefix}{i}" for prefix in ("charity_contact_address", "contact_address")
                      for i in range(1, 6)], "charity_contact_address", "contact_address"])
    source_address = pl.coalesce(company, registered, contact)
    selected = postcode(first(["RegAddress.PostCode", "registered_postcode", "postcode",
                               "charity_postcode", "charity_contact_postcode"]))
    entities = register.select(
        pl.int_range(pl.len(), dtype=pl.UInt32).alias("_source_row"),
        *[c for c in ("organisation_number", "registered_charity_number", "charity_name") if c in register.columns],
        source_address.alias("property_match_address"), selected.alias("property_match_postcode"),
        pl.when(company.is_not_null()).then(pl.lit("companies_house"))
        .when(registered.is_not_null()).then(pl.lit("registered_address"))
        .when(contact.is_not_null()).then(pl.lit("charity_commission"))
        .otherwise(None).alias("property_match_address_source"),
    )
    return expand_addresses(entities, "property_match_address", "property_match_postcode", "charity_name")


def active_charities(register: pl.DataFrame) -> pl.DataFrame:
    """Exclude charity rows with a nonmissing removal date."""
    return register.filter(text("date_of_removal").is_null()) if "date_of_removal" in register.columns else register


def deduplicate_charities(frame: pl.DataFrame) -> pl.DataFrame:
    """Prefer charity freeholders, then term estimates, completeness and input order."""
    columns = frame.columns
    complete = [pl.col(c).is_not_null() & (pl.col(c).cast(pl.String).str.strip_chars() != "")
                if frame.schema[c] == pl.String else pl.col(c).is_not_null() for c in columns]
    return (frame.with_row_index("_dedup_order").with_columns(
        pl.sum_horizontal([c.cast(pl.UInt32) for c in complete]).alias("_complete"),
        pl.col("lease_years_remaining").is_not_null().alias("_has_term"),
        (pl.col("charity_is_freeholder").fill_null(False)
         if "charity_is_freeholder" in columns else pl.lit(False)).alias("_freeholder"),
    ).sort(["_freeholder", "_has_term", "_complete", "_dedup_order"], descending=[True, True, True, False])
      .unique("registered_charity_number", keep="first", maintain_order=True)
      .sort("_dedup_order").select(columns))


def load_properties(path: Path, kind: str, wanted: pl.DataFrame) -> pl.DataFrame:
    """Stream the raw CSV and retain only property postcodes used by charities."""
    if kind not in PROPERTY_FIELDS:
        raise ValueError(f"Unknown property source: {kind}")
    raw = pl.scan_csv(local_path(path), infer_schema=False)
    columns = raw.collect_schema().names()
    # The supplied leases file has a malformed first header: easeUnique Identifier.
    aliases = {c: "Unique Identifier" for c in columns
               if c.strip().lower() in {"easeunique identifier", "leaseunique identifier"}}
    if aliases:
        raw = raw.rename(aliases)
        columns = raw.collect_schema().names()
    required = {"Property Address"} if kind == "ccod" else set()
    if missing := required - set(columns):
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    if kind == "lease" and not {"Associated Property Description", "Register Property Description"} & set(columns):
        raise ValueError(f"{path.name} needs Associated Property Description or Register Property Description")
    mapping = PROPERTY_FIELDS[kind]
    projected = raw.select([
        text(c).alias(f"{kind}_{name}") if c in columns
        else pl.lit(None, dtype=pl.String).alias(f"{kind}_{name}")
        for c, name in mapping.items()
    ])
    if kind == "lease":
        projected = projected.with_columns(
            pl.coalesce("lease_associated_property_description",
                        "lease_register_property_description").alias("lease_full_address")
        )
    full_address = text(f"{kind}_full_address")
    # Broad postcode prefilter before expensive address cleaning. The exact cleaner
    # then chooses the supplied postcode or splits multi-address records.
    postcodes = full_address.str.to_uppercase().str.extract_all(POSTCODE_PATTERN)
    if kind == "ccod":
        postcodes = pl.concat_list(text("ccod_postcode"), postcodes)
    projected = (
        projected.with_row_index("_raw_row")
        .with_columns(postcodes.alias("_postcode")).explode("_postcode", empty_as_null=True)
        .with_columns(postcode(pl.col("_postcode")).alias("_postcode"))
        .join(wanted.lazy().select(postcode(pl.col("postcode_clean")).alias("_postcode"))
              .drop_nulls().unique(), on="_postcode", how="semi")
        .unique("_raw_row", keep="first", maintain_order=True).drop("_postcode", "_raw_row")
    )
    frame = projected.collect(engine="streaming")
    if kind == "ccod":
        frame = frame.with_columns(pl.coalesce([
            pl.col(f"ccod_proprietor_name_{i}").map_elements(clean_owner_name, return_dtype=pl.String)
            for i in range(1, 5)]).alias("ccod_owner"))
    frame = expand_addresses(frame, f"{kind}_full_address", "ccod_postcode" if kind == "ccod" else None,
                             "ccod_owner" if kind == "ccod" else None)
    return frame.join(wanted.select("postcode_clean").drop_nulls().unique(),
                      on="postcode_clean", how="semi")


def match_properties(entities: pl.DataFrame, properties: pl.DataFrame, kind: str,
                     *, fuzzy: bool = True, min_score: float = 72.0) -> pl.DataFrame:
    """Use the shared weighted address/owner score, ranking and review thresholds."""
    if not 0 <= min_score <= 100:
        raise ValueError("min_score must be between 0 and 100")
    property_columns = [c for c in properties.columns if c.startswith(kind + "_")]
    targets = properties.sort(property_columns + ["address_expanded"]).with_row_index("_target_row")
    config = MatchConfig(entity_id_col="_source_row", target_id_col="_target_row", min_score=min_score)
    target_keys = targets.select("_target_row", *MATCH_COLUMNS).filter(pl.col("address_match_key").is_not_null())
    valid = entities.select("_source_row", *MATCH_COLUMNS).filter(pl.col("address_match_key").is_not_null())
    # Keep each source's expanded variants together, and bound candidate memory.
    parts = []
    source_ids = valid.select("_source_row").unique(maintain_order=True)
    for ids in source_ids.iter_slices(500):
        batch = valid.join(ids, on="_source_row", how="semi")
        candidates = build_postcode_candidates(batch, target_keys, config=config)
        if candidates.is_empty():
            continue
        if not fuzzy:
            candidates = candidates.filter(pl.col("address_match_key") == pl.col("address_match_key_target"))
        # One target variant can be reached from several charity address variants.
        ranked = rank_candidates(candidates, config=config)
        if ranked.is_empty():
            continue
        ranked = ranked.unique(["_source_row", "_target_row"], keep="first", maintain_order=True)
        ranked = ranked.with_columns(pl.int_range(pl.len()).over("_source_row").add(1).alias("candidate_rank"))
        best = select_best_matches(ranked, config=config).join(
            ranked.group_by("_source_row").len(name=f"{kind}_candidate_count"), on="_source_row")
        parts.append(best.select("_source_row", "_target_row", f"{kind}_candidate_count",
            *[pl.col(c).alias(f"{kind}_{c}") for c in
              ("match_score", "match_confidence", "match_type", "needs_manual_review")]))
    schema = {"_source_row": pl.UInt32, "_target_row": pl.UInt32,
              f"{kind}_candidate_count": pl.UInt32, f"{kind}_match_score": pl.Float64,
              f"{kind}_match_confidence": pl.String, f"{kind}_match_type": pl.String,
              f"{kind}_needs_manual_review": pl.Boolean}
    best = pl.concat(parts) if parts else pl.DataFrame(schema=schema)
    best = best.join(targets.select("_target_row", *property_columns), on="_target_row", how="left",
                     validate="m:1").drop("_target_row").with_columns(
        pl.lit(True).alias("ccod_matched" if kind == "ccod" else "registered_lease_matched"))
    if kind == "lease":
        best = best.with_columns(
            pl.col("lease_full_address").alias("registered_lease_full_address"),
            pl.col("lease_unique_identifier").alias("registered_lease_unique_identifier"),
            pl.col("lease_uprn").alias("registered_lease_uprn"))
    return best


def merge_matches(register: pl.DataFrame, entities: pl.DataFrame,
                  matches: list[pl.DataFrame]) -> pl.DataFrame:
    """Preserve original rows, columns and types; never merge by charity number."""
    result = register.with_row_index("_source_row")
    additions = [entities.select("_source_row", "property_match_address",
                                 "property_match_postcode", "property_match_address_source").unique("_source_row", keep="first", maintain_order=True), *matches]
    for part in additions:
        overlap = (set(part.columns) - {"_source_row"}) & set(result.columns)
        if overlap:
            raise ValueError(f"Input already contains output columns: {sorted(overlap)}")
        result = result.join(part, on="_source_row", how="left",
                             validate="1:1", maintain_order="left")
    return result.with_columns(
        pl.col("ccod_matched", "registered_lease_matched").fill_null(False),
        pl.col("ccod_candidate_count", "lease_candidate_count").fill_null(0),
        pl.col("ccod_needs_manual_review", "lease_needs_manual_review").fill_null(False),
    ).with_columns(
        (pl.col("ccod_needs_manual_review") | pl.col("lease_needs_manual_review")).alias("review")
    ).drop("_source_row")
