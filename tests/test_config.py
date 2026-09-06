"""Ensure the shared configuration reaches both readers and downloaders."""

import subprocess
import sys
import unittest


class ConfigurationTests(unittest.TestCase):
    def test_custom_sources_and_endpoint(self):
        # Isolate module reloads so the other tests retain the normal settings.
        script = '''
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import polars as pl
from uk_charity_local_authority_analysis.core import config, charity
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup import datasets, endpoint

with TemporaryDirectory() as directory:
    root = Path(directory)
    config.CHARITY = root / "custom_charities.csv"
    config.CHARITY.write_text("registered_charity_number\\n001234\\n")
    config.ONS_RAW_DIR = root / "custom_ons"
    config.ONS_OUTPUT_PATH = root / "custom_lookup.parquet"
    config.CHARITY_OUTPUT_PATH = root / "custom_register.parquet"
    config.ONS_POSTCODE_LOOKUP_URL = "https://example.org/custom.zip"
    config.ONS_POSTCODE_LOOKUP_FILENAME = "custom.zip"
    config.ONS_SOURCE_CSV = root / "custom_postcodes.csv"
    config.ONS_SOURCE_CSV.write_text("pcds,lad25cd,rgn25cd\\nAB1 2CD,LAD1,RGN1\\n")
    importlib.reload(endpoint)
    importlib.reload(datasets)
    importlib.reload(charity)
    assert charity.load_charity()["registered_charity_number"][0] == "001234"
    assert charity.DEFAULT_OUTPUT_PATH == config.CHARITY_OUTPUT_PATH
    assert charity.ONS == config.ONS_OUTPUT_PATH
    with patch.object(datasets, "download_file") as download:
        datasets.download_ons_postcode_lookup()
        download.assert_called_once_with(config.ONS_POSTCODE_LOOKUP_URL,
            dest_dir=config.ONS_RAW_DIR, filename="custom.zip")
    assert datasets.build_ons_postcode_lookup() == config.ONS_OUTPUT_PATH
    assert charity.load_ons()["pcds"][0] == "AB1 2CD"
    config.ONS_SOURCE_CSV.write_text("pcds,lad25cd,rgn25cd\\nXY1 2ZZ,LAD2,RGN2\\n")
    datasets.build_ons_postcode_lookup()
    assert pl.read_parquet(config.ONS_OUTPUT_PATH)["pcd"][0] == "XY1 2ZZ"
    config.ONS_SOURCE_CSV.unlink()
    try:
        datasets.build_ons_postcode_lookup()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Missing configured CSV silently used cached output")
'''
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
