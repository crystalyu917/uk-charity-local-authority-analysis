"""Compatibility exports; edit the ONS endpoint in core/config.py."""

from uk_charity_local_authority_analysis.core.config import (
    ONS_POSTCODE_LOOKUP_FILENAME,
    ONS_POSTCODE_LOOKUP_ITEM_ID,
    ONS_POSTCODE_LOOKUP_URL,
)

__all__ = [
    "ONS_POSTCODE_LOOKUP_FILENAME",
    "ONS_POSTCODE_LOOKUP_ITEM_ID",
    "ONS_POSTCODE_LOOKUP_URL",
]
