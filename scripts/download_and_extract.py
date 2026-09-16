"""Download and extract all datasets, or only the supplied source names."""

import argparse
from datetime import date
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uk_charity_local_authority_analysis.charity_commission_register.config import (
    CHARITY_COMMISSION_CHARITY_URL,
    CHARITY_COMMISSION_CLASSIFICATION_URL,
    ONS_POSTCODE_LOOKUP_URL,
    UTLA_LOOKUP_URL,
    UTLA_ARCHIVE_FILENAME,
)
from uk_charity_local_authority_analysis.charity_commission_register.download_and_extract import (
    download_file,
    extract_zip,
)

DATA_DIR = PROJECT_ROOT / "data" / "charity_commission_register"
# Source name: URL, source directory, filename. The download date is appended.
SOURCES = {
    "utla": (UTLA_LOOKUP_URL, DATA_DIR / "utla_lookup", UTLA_ARCHIVE_FILENAME),
    "ons": (ONS_POSTCODE_LOOKUP_URL, DATA_DIR / "ons", "ONSPD_MAY_2026.zip"),
    "charity": (
        CHARITY_COMMISSION_CHARITY_URL, DATA_DIR / "charity_commission", "publicextract.charity.zip",
    ),
    "classification": (
        CHARITY_COMMISSION_CLASSIFICATION_URL, DATA_DIR / "charity_commission",
        "publicextract.charity_classification.zip",
    ),
    "company_house": (
        "https://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-2026-09-01.zip",
        DATA_DIR / "company_house",
        "BasicCompanyDataAsOneFile-2026-09-01.zip",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources", nargs="*", metavar="SOURCE",
        help=f"Sources to download: {', '.join(SOURCES)}. Omit to download all.",
    )
    args = parser.parse_args()
    unknown = [name for name in args.sources if name not in SOURCES]
    if unknown:
        parser.error(f"Unknown sources: {', '.join(unknown)}. Choose from: {', '.join(SOURCES)}")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    download_date = date.today().strftime("%d%m%Y")
    selected = list(dict.fromkeys(args.sources)) if args.sources else list(SOURCES)
    failed = []
    for name in selected:
        url, folder, filename = SOURCES[name]
        destination = folder / download_date
        print(f"Downloading {name}", flush=True)
        try:
            downloaded_path = download_file(
                url, dest_dir=destination, filename=filename, refresh=True,
            )
            print(downloaded_path)
            if downloaded_path.suffix.lower() == ".zip":
                extracted_paths = extract_zip(downloaded_path, refresh=True)
                print(f"Extracted {len(extracted_paths)} files to {downloaded_path.with_suffix('')}")
        except Exception as error:
            print(f"{name} failed: {error}", file=sys.stderr)
            failed.append(name)

    if failed:
        print(f"Download or extraction failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("All selected downloads and extracted files have been refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
