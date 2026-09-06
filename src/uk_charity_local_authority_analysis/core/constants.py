"""Paths shared by core dataset utilities."""

from pathlib import Path
from typing import Final

PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR: Final = PROJECT_ROOT / "data" / "core"
DEFAULT_STAGING_DIR: Final = PROJECT_ROOT / "data" / "core" / "staging"
OUTPUT_DIR = PROJECT_ROOT / "data" / "core" / "output"
