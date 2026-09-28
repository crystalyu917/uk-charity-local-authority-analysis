"""Download and extract all datasets, or only the supplied source names."""

import argparse
from datetime import date
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uk_charity_local_authority_analysis.charity_commission_register.settings import (
    CONFIG_PATH, load_settings, download_settings,
)
from uk_charity_local_authority_analysis.charity_commission_register.download_and_extract import (
    download_file,
    extract_zip,
)



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources", nargs="*", metavar="SOURCE",
        help="Configured source names. Omit to download all.",
    )
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    try:
        sources, overwrite = download_settings(load_settings(args.config))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    unknown = [name for name in args.sources if name not in sources]
    if unknown:
        parser.error(f"Unknown sources: {', '.join(unknown)}. Choose from: {', '.join(sources)}")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    download_date = date.today().strftime("%d%m%Y")
    selected = list(dict.fromkeys(args.sources)) if args.sources else list(sources)
    failed = []
    for name in selected:
        url, folder, filename = sources[name]
        destination = folder / download_date
        print(f"Downloading {name}", flush=True)
        try:
            downloaded_path = download_file(
                url, dest_dir=destination, filename=filename, refresh=overwrite,
            )
            print(downloaded_path)
            if downloaded_path.suffix.lower() == ".zip":
                extracted_paths = extract_zip(downloaded_path, refresh=overwrite)
                print(f"Extracted {len(extracted_paths)} files to {downloaded_path.with_suffix('')}")
        except Exception as error:
            print(f"{name} failed: {error}", file=sys.stderr)
            failed.append(name)

    if failed:
        print(f"Download or extraction failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("All selected downloads and extractions completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
