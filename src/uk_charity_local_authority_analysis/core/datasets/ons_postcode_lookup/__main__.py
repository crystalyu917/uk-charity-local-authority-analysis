"""Download, extract, or build the repository's ONS postcode lookup."""

import argparse
import logging

from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup.datasets import (
    build_ons_postcode_lookup,
    download_ons_postcode_lookup,
    extract_ons_postcode_lookup,
)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", nargs="?", choices=("download", "extract", "build"),
        default="build", help="Action to run (default: build).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.action == "download":
        print(download_ons_postcode_lookup())
    elif args.action == "extract":
        files = extract_ons_postcode_lookup()
        for path in (files.postcode, files.lad, files.region):
            print(path)
    else:
        print(build_ons_postcode_lookup())


if __name__ == "__main__":
    main()
