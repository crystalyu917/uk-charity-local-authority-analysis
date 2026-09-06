"""Compatibility exports; edit data settings in core/config.py."""

from uk_charity_local_authority_analysis.core.config import (
    DEFAULT_DATA_DIR,
    DEFAULT_STAGING_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
)

__all__ = ["DEFAULT_DATA_DIR", "DEFAULT_STAGING_DIR", "OUTPUT_DIR", "PROJECT_ROOT"]
