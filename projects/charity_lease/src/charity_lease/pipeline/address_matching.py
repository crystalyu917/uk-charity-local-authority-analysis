"""Reusable matching utilities for entity and target address matching."""

from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass
from difflib import SequenceMatcher

import polars as pl


@dataclass(frozen=True)
class MatchConfig:
    """Column names and thresholds used by the matching pipeline."""

    entity_id_col: str = "entity_row_id"
    target_id_col: str = "target_row_id"
    postcode_col: str = "postcode_clean"
    min_score: float = 72.0
    best_score_gap: float = 3.0
    max_candidates_per_entity: int = 10


ADDRESS_STOPWORDS = {
    "A",
    "AN",
    "AND",
    "AT",
    "ENGLAND",
    "GREAT",
    "LONDON",
    "OF",
    "THE",
    "UK",
    "UNITED",
    "WALES",
}


@lru_cache(maxsize=4096)
def normalise_match_text(value: object) -> str:
    """Normalize text for fuzzy scoring."""
    if value is None:
        return ""
    text = str(value).upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def address_tokens(value: object) -> set[str]:
    """Tokenize an address, dropping low-signal location/filler words."""
    return {
        token
        for token in normalise_match_text(value).split()
        if token and token not in ADDRESS_STOPWORDS
    }


def building_numbers(value: object) -> set[str]:
    """Return building number-like tokens from an address."""
    return set(re.findall(r"\b\d+[A-Z]?\b", normalise_match_text(value)))


@lru_cache(maxsize=4096)
def token_set_ratio(left: object, right: object) -> float:
    """Small dependency-free token-set similarity score from 0 to 100."""
    left_tokens = address_tokens(left)
    right_tokens = address_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = left_tokens & right_tokens
    left_only = left_tokens - intersection
    right_only = right_tokens - intersection

    sorted_intersection = " ".join(sorted(intersection))
    left_combined = " ".join(sorted(intersection | left_only))
    right_combined = " ".join(sorted(intersection | right_only))

    scores = [
        SequenceMatcher(None, sorted_intersection, left_combined).ratio(),
        SequenceMatcher(None, sorted_intersection, right_combined).ratio(),
        SequenceMatcher(None, left_combined, right_combined).ratio(),
    ]
    return max(scores) * 100


@lru_cache(maxsize=4096)
def sequence_ratio(left: object, right: object) -> float:
    """Ordered string similarity score from 0 to 100."""
    left_text = normalise_match_text(left)
    right_text = normalise_match_text(right)
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio() * 100


@lru_cache(maxsize=4096)
def owner_ratio(left: object, right: object) -> float:
    """Owner-name similarity score from 0 to 100."""
    return max(token_set_ratio(left, right), sequence_ratio(left, right))


def _first_non_missing(*values: object) -> object:
    """Return the first non-null/non-NA value from a list of candidates."""
    for value in values:
        if (
            value is None
            or value == ""
            or (isinstance(value, float) and value != value)
        ):
            continue
        return value
    return None


def _score_candidate_row(row_dict: dict) -> dict:
    """Score one entity/target candidate pair from a dictionary representation."""
    entity_address = _first_non_missing(
        row_dict.get("address_expanded"),
        row_dict.get("address_clean"),
        row_dict.get("address_expanded_target"),
        row_dict.get("address_clean_target"),
    )
    target_address = _first_non_missing(
        row_dict.get("address_expanded_target"),
        row_dict.get("address_clean_target"),
        row_dict.get("address_expanded"),
        row_dict.get("address_clean"),
    )
    entity_owner = _first_non_missing(
        row_dict.get("owner_clean"),
        row_dict.get("owner_clean_target"),
    )
    target_owner = _first_non_missing(
        row_dict.get("owner_clean_target"),
        row_dict.get("owner_clean"),
    )

    address_token_score = token_set_ratio(entity_address, target_address)
    address_order_score = sequence_ratio(entity_address, target_address)
    address_score = (address_token_score * 0.75) + (address_order_score * 0.25)
    owner_score = owner_ratio(entity_owner, target_owner)

    entity_numbers = building_numbers(entity_address)
    target_numbers = building_numbers(target_address)
    number_match = bool(
        entity_numbers
        and target_numbers
        and entity_numbers.intersection(target_numbers)
    )
    number_conflict = bool(
        entity_numbers
        and target_numbers
        and not entity_numbers.intersection(target_numbers)
    )

    owner_key_entity = normalise_match_text(row_dict.get("owner_address_match_key"))
    owner_key_target = normalise_match_text(
        row_dict.get("owner_address_match_key_target")
    )
    address_key_entity = normalise_match_text(row_dict.get("address_match_key"))
    address_key_target = normalise_match_text(row_dict.get("address_match_key_target"))
    exact_owner_address = bool(
        owner_key_entity and owner_key_entity == owner_key_target
    )
    exact_address = bool(
        address_key_entity and address_key_entity == address_key_target
    )

    score = address_score
    if exact_owner_address:
        score = 100.0
    elif exact_address:
        score = max(score, 96.0)
    else:
        if number_match:
            score += 6.0
        if owner_score >= 92:
            score += 5.0
        elif owner_score >= 80:
            score += 3.0
        if number_conflict:
            score = min(score - 12.0, 68.0)

    score = max(0.0, min(100.0, score))
    if score >= 95:
        confidence = "high"
    elif score >= 84:
        confidence = "medium"
    else:
        confidence = "review"

    return {
        "match_score": round(score, 2),
        "address_score": round(address_score, 2),
        "owner_score": round(owner_score, 2),
        "building_number_match": number_match,
        "building_number_conflict": number_conflict,
        "exact_owner_address_key": exact_owner_address,
        "exact_address_key": exact_address,
        "match_confidence": confidence,
    }


def build_postcode_candidates(
    entity: pl.DataFrame,
    target: pl.DataFrame,
    *,
    config: MatchConfig = MatchConfig(),
) -> pl.DataFrame:
    """Build candidate pairs by blocking on cleaned postcode."""
    if (
        config.postcode_col not in entity.columns
        or config.postcode_col not in target.columns
    ):
        raise KeyError(f"Both inputs must contain {config.postcode_col!r}.")

    entity_block = entity.filter(pl.col(config.postcode_col).is_not_null())
    target_block = target.filter(pl.col(config.postcode_col).is_not_null())

    if entity_block.height == 0 or target_block.height == 0:
        return pl.DataFrame()

    # Strip postcodes
    entity_block = entity_block.with_columns(
        pl.col(config.postcode_col)
        .cast(pl.Utf8)
        .str.strip_chars()
        .alias(config.postcode_col)
    )
    target_block = target_block.with_columns(
        pl.col(config.postcode_col)
        .cast(pl.Utf8)
        .str.strip_chars()
        .alias(config.postcode_col)
    )

    # Get postcodes present in entity data
    wanted_postcodes = (
        entity_block.select(config.postcode_col).unique().to_series().to_list()
    )
    target_block = target_block.filter(
        pl.col(config.postcode_col).is_in(wanted_postcodes)
    )

    if target_block.height == 0:
        return pl.DataFrame()

    return entity_block.join(
        target_block,
        on=config.postcode_col,
        how="inner",
        suffix="_target",
    )


def rank_candidates(
    candidates: pl.DataFrame,
    *,
    config: MatchConfig = MatchConfig(),
) -> pl.DataFrame:
    """Score and rank postcode-blocked candidates."""
    if candidates.height == 0:
        return candidates

    # Convert to list of dicts, score each, then add back to dataframe
    rows = candidates.to_dicts()
    scored_rows = [_score_candidate_row(row) for row in rows]

    # Create a dataframe from scored results
    score_df = pl.DataFrame(scored_rows)

    # Combine with original candidates
    scored = candidates.hstack(score_df)

    # Filter by minimum score
    scored = scored.filter(pl.col("match_score") >= config.min_score)

    if scored.height == 0:
        return scored


    # Sort and rank
    scored = scored.sort(
        [config.entity_id_col, "match_score", "owner_score", "address_score"],
        descending=[False, True, True, True],
    )

    scored = scored.with_columns(
        pl.int_range(pl.len()).over(config.entity_id_col).add(1).alias("candidate_rank")
    )

    return scored.filter(pl.col("candidate_rank") <= config.max_candidates_per_entity)


def select_best_matches(
    ranked: pl.DataFrame,
    *,
    config: MatchConfig = MatchConfig(),
) -> pl.DataFrame:
    """Return the best candidate for each entity row and flag close alternatives."""
    if ranked.height == 0:
        return ranked

    best = ranked.filter(pl.col("candidate_rank") == 1)

    second = ranked.filter(pl.col("candidate_rank") == 2).select(
        [config.entity_id_col, pl.col("match_score").alias("second_best_score")]
    )

    best = best.join(second, on=config.entity_id_col, how="left")

    best = best.with_columns(
        (pl.col("match_score") - pl.col("second_best_score").fill_null(0)).alias(
            "score_gap_to_second"
        )
    )

    weak_non_exact_owner = (
        ~pl.col("exact_address_key").fill_null(False)
        & ~pl.col("exact_owner_address_key").fill_null(False)
        & (pl.col("owner_score") < 50)
        & (pl.col("match_score") < 98)
    )

    best = best.with_columns(
        (
            (pl.col("match_confidence") != "high")
            | (pl.col("score_gap_to_second") < config.best_score_gap)
            | pl.col("building_number_conflict").fill_null(False)
            | weak_non_exact_owner
        ).alias("needs_manual_review")
    )

    # Add match_type based on scores
    best = best.with_columns(
        pl.when(pl.col("exact_owner_address_key"))
        .then(pl.lit("exact_owner_address"))
        .when(pl.col("exact_address_key"))
        .then(pl.lit("exact_address"))
        .when((pl.col("match_score") >= 96) & (pl.col("address_score") >= 94))
        .then(pl.lit("near_exact_address"))
        .otherwise(pl.lit("postcode_ranked_similarity"))
        .alias("match_type")
    )

    return best


