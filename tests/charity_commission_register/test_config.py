"""Explicit filepaths reach readers, builders, and run records."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import polars as pl

from importlib import import_module

charity = import_module("uk_charity_local_authority_analysis.charity_commission_register.build_charity_register")
from uk_charity_local_authority_analysis.charity_commission_register import ons as datasets


class ConfigurationTests(unittest.TestCase):
    def test_explicit_local_ons_sources(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "custom_postcodes.csv"
            output = root / "custom_lookup.parquet"
            source.write_text("pcds,lad25cd,rgn25cd\nAB1 2CD,LAD1,RGN1\n")
            datasets.build_ons_postcode_lookup(output, source)
            self.assertEqual(charity.load_ons(output)["pcds"][0], "AB1 2CD")
            source.write_text("pcds,lad25cd,rgn25cd\nXY1 2ZZ,LAD2,RGN2\n")
            datasets.build_ons_postcode_lookup(output, source)
            self.assertEqual(pl.read_parquet(output)["pcd"][0], "XY1 2ZZ")
            source.unlink()
            with self.assertRaises(FileNotFoundError):
                datasets.build_ons_postcode_lookup(output, source)

    def test_build_forwards_and_records_every_input_filepath(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                "charity_filepath": root / "charity.csv",
                "classification_filepath": root / "classification.csv",
                "company_house_filepath": root / "companies.csv",
                "find_that_charity_filepath": root / "find.csv",
                "ons_filepath": root / "ons.parquet",
                "utla_filepath": root / "utla.csv",
            }
            with patch.object(charity, "load_charity_register", return_value=pl.DataFrame({"id": [1]})) as load:
                saved = charity.build_charity_register(root / "output" / "register.parquet", **paths)
                load.assert_called_once_with(**paths)
            record = json.loads(saved.with_suffix(".run.json").read_text())
            for label, argument in (
                ("charity_commission", "charity_filepath"),
                ("charity_classification", "classification_filepath"),
                ("companies_house", "company_house_filepath"),
                ("find_that_charity", "find_that_charity_filepath"),
                ("ons_lookup", "ons_filepath"),
                ("utla_lookup", "utla_filepath"),
            ):
                self.assertEqual(record["inputs"][label]["path"], str(paths[argument].resolve()))


if __name__ == "__main__":
    unittest.main()
