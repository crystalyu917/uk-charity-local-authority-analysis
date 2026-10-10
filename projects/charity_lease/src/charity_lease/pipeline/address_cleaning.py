"""Address and proprietor normalisation for the single property-matching pipeline."""

from __future__ import annotations

import re
from functools import lru_cache

import math

UK_POSTCODE_RE = re.compile(
    r"\b(?:[A-Z][A-HJ-Y]?\d[\dA-Z]?\s?\d[A-Z]{2}|GIR\s?0AA)\b",
    flags=re.IGNORECASE,
)

LEGAL_NOISE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bAIR ?SPACE\b", " "),
    (r"\bMINES? AND MINERALS?\b", " "),
    (r"\bSUB[- ]?STATION\b", "SUBSTATION"),
    (r"\bADJOING|ADJOININGIN|ADJOININING|ADJOINNG|ADJONING|AJOINING\b", "ADJOINING"),
    (r"\bSITUATE\b", "SITUATED"),
    (r"\bTHE SITE OF\b", " "),
    (r"\bPARTS? OF\b", " "),
    (r"\bLAND LYING TO THE\b", "LAND "),
    (r"\bLAND LYING\b", "LAND "),
    (r"\bLAND AND BUILDINGS?\b", "LAND "),
    (r"\bLAND AND PREMISES\b", "LAND "),
    (r"\bASSOCIATED LAND AND BUILDINGS?\b", " "),
    (r"\bNUMBERED \d+ ON THE FILED PLAN\b", " "),
    (r"\bSHOWN (EDGED|TINTED|COLOURED) [A-Z]+ ON THE FILED PLAN\b", " "),
    (r"\bFILED PLAN\b", " "),
)

ADDRESS_WORD_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bROAD\b", "RD"),
    (r"\bSTREET\b", "ST"),
    (r"\bAVENUE\b", "AVE"),
    (r"\bLANE\b", "LN"),
    (r"\bDRIVE\b", "DR"),
    (r"\bCLOSE\b", "CL"),
    (r"\bCOURT\b", "CT"),
    (r"\bPLACE\b", "PL"),
    (r"\bGARDENS\b", "GDNS"),
    (r"\bAPARTMENT\b", "APT"),
    (r"\bFLAT\b", "FLT"),
    (r"\bBUILDING\b", "BLDG"),
    (r"\bFLOOR\b", "FLR"),
    (r"\bGROUND FLOOR\b", "GND FLR"),
)

MISSING_MARKERS = {"", "-", "?", "N/A", "NA", "NONE", "NULL", "NAN"}


def is_missing(value: object) -> bool:
    """Return True for scalar missing values and common placeholder strings."""
    if value is None:
        return True
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip().upper() in MISSING_MARKERS:
        return True
    return False


@lru_cache(maxsize=4096)
def squish(value: object) -> str | None:
    """Convert blanks to None and collapse whitespace."""
    if is_missing(value):
        return None
    text = str(value).replace("\u00a0", " ")
    text = (
        text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore") or text
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


@lru_cache(maxsize=4096)
def norm_text(value: object, *, upper: bool = True) -> str | None:
    """Normalize punctuation, whitespace, and mojibake quote variants."""
    text = squish(value)
    if text is None:
        return None

    replacements = {
        "Ã¢â‚¬Ëœ": "'",
        "Ã¢â‚¬â„¢": "'",
        "Ã¢â‚¬Å“": '"',
        "Ã¢â‚¬": '"',
        "`": "'",
        "â€“": "-",
        "â€”": "-",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    if upper:
        text = text.upper()
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text or None


@lru_cache(maxsize=4096)
def extract_postcode(value: object) -> str | None:
    """Return the last UK postcode in normalized outward/inward format."""
    text = norm_text(value)
    if text is None:
        return None
    matches = UK_POSTCODE_RE.findall(text)
    if not matches:
        return None
    return format_postcode(matches[-1])


@lru_cache(maxsize=4096)
def format_postcode(value: object) -> str | None:
    """Normalize a postcode-like value to 'OUT INN' format."""
    text = norm_text(value)
    if text is None:
        return None
    compact = re.sub(r"[^A-Z0-9]", "", text.upper())
    if len(compact) < 5:
        return None
    if not UK_POSTCODE_RE.fullmatch(compact) and not UK_POSTCODE_RE.fullmatch(text):
        return None
    return f"{compact[:-3]} {compact[-3:]}"


def split_address_sections_by_postcode(value: object) -> list[tuple[str, str]]:
    """Split a multi-postcode address at postcode boundaries."""
    text = norm_text(value)
    if text is None:
        return []
    matches = list(UK_POSTCODE_RE.finditer(text))
    if len(matches) <= 1:
        pc = format_postcode(matches[-1].group(0)) if matches else None
        return [(text, pc)] if pc else []

    sections: list[tuple[str, str]] = []
    start = 0
    for match in matches:
        section = text[start : match.end()]
        pc = format_postcode(match.group(0))
        cleaned = clean_section_edges(section)
        if cleaned and pc:
            sections.append((cleaned, pc))
        start = match.end()
    return sections


@lru_cache(maxsize=4096)
def clean_section_edges(value: object) -> str | None:
    """Clean leading/trailing punctuation left by multi-postcode splitting."""
    text = norm_text(value)
    if text is None:
        return None
    text = re.sub(r"^(?:AND\s+|[,;&/().\-\s]+AND\s+|[,;&/().\-\s]+)+", "", text)
    text = re.sub(r"(?:[,;&/().\-\s]+)$", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;-/()")
    return text or None


@lru_cache(maxsize=4096)
def remove_postcode(value: object, postcode: object = None) -> str | None:
    """Remove a supplied postcode and any postcode-looking substrings."""
    text = norm_text(value)
    if text is None:
        return None

    pc = extract_postcode(postcode) or format_postcode(postcode)
    if pc:
        text = text.replace(pc, "")
        text = text.replace(pc.replace(" ", ""), "")

    text = UK_POSTCODE_RE.sub("", text)
    return clean_section_edges(text)


@lru_cache(maxsize=4096)
def clean_land_registry_phrases(value: object) -> str | None:
    """Remove/standardise legal phrases used heavily in LR address descriptions."""
    text = norm_text(value)
    if text is None:
        return None

    for pattern, replacement in LEGAL_NOISE_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(
        r"\b(?:THE|ON THE)?\s*(?:NORTH|SOUTH|EAST|WEST|NORTH EAST|NORTH WEST|SOUTH EAST|SOUTH WEST)"
        r"(?:ERN|ERLY)?\s+(?:SIDE|SIDES|CORNER|BOUNDARY|JUNCTION)\s+OF\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:LOWER GROUND|GROUND|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|TOP)"
        r"\s+FLOOR\s+(?:FLATS?|APARTMENTS?|PREMISES|OFFICES?)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b\d{1,2}[- /.]\d{1,2}[- /.](?:19|20)\d{2}\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text or None


@lru_cache(maxsize=4096)
def clean_owner_name(value: object) -> str | None:
    """Normalize owner/proprietor names for matching."""
    text = norm_text(value)
    if text is None:
        return None
    text = re.sub(r"\b(PUBLIC LIMITED COMPANY|PLC\.?)\b", "PLC", text)
    text = re.sub(r"\b(LIMITED|LTD\.?)\b", "LTD", text)
    text = re.sub(r"\b(THE BOROUGH COUNCIL OF|BOROUGH COUNCIL OF)\b", "", text)
    text = re.sub(r"[^A-Z0-9\s&'/-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return None if text in MISSING_MARKERS else text or None


@lru_cache(maxsize=4096)
def standardise_address_words(value: object, postcode: object = None) -> str | None:
    """Remove postcode and standardise common address tokens."""
    text = remove_postcode(value, postcode)
    text = clean_land_registry_phrases(text)
    if text is None:
        return None

    for pattern, replacement in ADDRESS_WORD_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"[^A-Z0-9\s,/'&().@-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text or None


def _normalise_range_modifiers(value: str) -> str:
    """Collapse variants of inclusive/odd/even markers."""
    value = re.sub(r"\bNUMBERES|NOMBERS\b", "NUMBERS", value, flags=re.I)
    value = re.sub(
        r"\b(?:INCLUSIVE\s*)?\(?\s*ODD(?:\s+NOS?|\s+NO'?S|\s+NUMBERS?)?(?:\s+ONLY|\s+INCLUSIVE)?\s*\)?",
        "(ODD)",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\b(?:INCLUSIVE\s*)?\(?\s*EVEN(?:\s+NOS?|\s+NO'?S|\s+NUMBERS?)?(?:\s+ONLY|\s+INCLUSIVE)?\s*\)?",
        "(EVN)",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\((?:\s*INC[^)]*|\s*INCL[^)]*|\s*ALL[^)]*|\s*CONSEC[^)]*|\s*BOTH INCLUSIVE[^)]*)\)",
        "(INC)",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\b(INCLUSIVE|INC|INCL|CONSECUTIVE|BOTH INCLUSIVE|ALL INCLUSIVE)\b",
        "(INC)",
        value,
        flags=re.I,
    )
    value = re.sub(r"\bNOS?\b", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def split_numbers(value: object, *, max_expansion: int = 250) -> list[str]:
    """Expand simple multi-number addresses into candidate address strings."""
    address = standardise_address_words(value)
    if address is None:
        return []

    if len(re.findall(r"\d+", address)) <= 1:
        return [address]
    if len(re.findall(r"\d+", address)) == 2 and re.search(
        r"\bUNIT\b", address, flags=re.I
    ):
        return [address]

    address = _normalise_range_modifiers(address)

    range_match = re.match(
        r"^\s*(\d+[A-Z]?)\s*(?:-|\bTO\b)\s*(\d+[A-Z]?)\s*(\((?:INC|ODD|EVN)\))?\s+(.+)$",
        address,
        flags=re.I,
    )
    if range_match:
        start, end, modifier, rest = range_match.groups()
        start_n = int(re.sub(r"\D", "", start))
        end_n = int(re.sub(r"\D", "", end))
        if 0 < abs(end_n - start_n) <= max_expansion:
            step = 1 if end_n >= start_n else -1
            nums = list(range(start_n, end_n + step, step))
            if modifier == "(ODD)":
                nums = [n for n in nums if n % 2 == 1]
            elif modifier == "(EVN)":
                nums = [n for n in nums if n % 2 == 0]
            return [f"{n} {rest}".strip() for n in nums]

    list_match = re.match(
        r"^\s*((?:\d+[A-Z]?\s*(?:,|AND|&|/)\s*)+\d+[A-Z]?)\s+(.+)$",
        address,
        flags=re.I,
    )
    if list_match:
        number_blob, rest = list_match.groups()
        nums = [n for n in re.split(r"\s*(?:,|AND|&|/)\s*", number_blob) if n]
        if len(nums) <= max_expansion:
            return [f"{n} {rest}".strip() for n in nums]

    return [address]


@lru_cache(maxsize=4096)
def make_address_match_key(address: object, postcode: object = None) -> str | None:
    """Build a normalized address + postcode match key."""
    address_clean = standardise_address_words(address, postcode)
    if address_clean is None:
        return None
    pc = extract_postcode(postcode) or extract_postcode(address)
    key = re.sub(r"[^A-Z0-9\s]", " ", address_clean)
    key = re.sub(r"\s+", " ", key).strip()
    return f"{key} | {pc}" if pc and key else key or None


