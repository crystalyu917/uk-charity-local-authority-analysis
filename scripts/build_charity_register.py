"""Prepare ONSPD geography and build the charity register."""

import argparse
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uk_charity_local_authority_analysis.charity_commission_register import (
    build_charity_register,
)
from uk_charity_local_authority_analysis.charity_commission_register.onspd import build_onspd_postcode_lookup
from uk_charity_local_authority_analysis.charity_commission_register.utla import latest_utla_lookup

from uk_charity_local_authority_analysis.charity_commission_register.settings import (
    CONFIG_PATH, load_settings, build_settings,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--target", help="Override build.target in config.json for this run.")
    args = parser.parse_args()
    try:
        paths = build_settings(load_settings(args.config), args.target)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    utla_filepath = paths["utla_filepath"]
    if utla_filepath is None:
        utla_filepath = latest_utla_lookup(paths["utla_directory"])
    onspd_filepath = build_onspd_postcode_lookup(
        output_path=paths["onspd_lookup_filepath"],
        source_csv=paths["onspd_source_csv_filepath"],
        archive_filepath=paths["onspd_archive_filepath"],
    )
    print(onspd_filepath)
    register_filepath = build_charity_register(
        output_path=paths["output_path"],
        charity_filepath=paths["charity_filepath"],
        classification_filepath=paths["classification_filepath"],
        company_house_filepath=paths["company_house_filepath"],
        find_that_charity_filepath=paths["find_that_charity_filepath"],
        onspd_filepath=onspd_filepath,
        utla_filepath=utla_filepath,
    )
    print(register_filepath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
