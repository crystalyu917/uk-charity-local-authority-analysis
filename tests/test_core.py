"""Integration regressions for the charity snapshot pipeline."""

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import polars as pl

from uk_charity_local_authority_analysis.core import charity as core


class CharityPipelineTests(unittest.TestCase):
    def test_merge_keeps_main_records_and_register_namespaces(self):
        charities = pl.DataFrame({
            "registered_charity_number": ["1", "1", "2", "3"],
            "linked_charity_number": ["0", "1", "0", "0"],
            "charity_company_registration_number": ["1234567", None, None, None],
            "date_of_registration": ["2020-03-31", "2020-03-31", "01/04/2020", None],
            "date_of_removal": [None, "2021-05-01", "2024-03-31", None],
            "charity_has_land": ["TRUE", "FALSE", "false", None],
            "latest_income": ["24999", "0", "25000", "1000001"],
            "charity_contact_postcode": ["WRONG", None, " ab1 2cd ", "NONE"],
        })
        classifications = pl.DataFrame({
            "registered_charity_number": ["1", "1"],
            "classification_description": ["Makes Grants To Individuals"] * 2,
        })
        companies = pl.DataFrame({
            " CompanyNumber": ["01234567"],
            "RegAddress.PostCode": [" sw1a 1aa "],
        })
        ftc = pl.DataFrame({
            "charityNumber": ["1", "1", "2", "3"],
            "source": ["ccew", "ccni", "ccew", "ccew"],
            "postalCode": ["OTHER", "WRONG", None, "xy1\t2zz"],
        })
        ons = pl.DataFrame({
            "pcds": ["SW1A 1AA", "AB1 2CD", "XY1 2ZZ"],
            "lad25cd": ["LAD1", "LAD2", "LAD3"],
        })
        result = core.merge_charity_data(
            charities, classifications, companies, ftc, ons
        ).sort("registered_charity_number")
        self.assertEqual(result.height, 3)
        self.assertEqual(result["local_authority_code"].to_list(), ["LAD1", "LAD2", "LAD3"])
        self.assertEqual(result["charity_status"].to_list(), ["active", "inactive", "active"])
        self.assertEqual(result["registration_fy"].to_list(), [2019, 2020, None])
        self.assertEqual(result["removal_fy"].to_list(), [None, 2023, None])
        self.assertEqual(result["size_category"].to_list(), ["Small", "Medium", "Large"])
        self.assertEqual(result["Grantmaking_And_Financial_Support"].to_list(), [1, 0, 0])
        self.assertEqual(result["charity_company_registration_number"][0], "01234567")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "register.parquet"
            result.write_parquet(path)
            self.assertEqual(core.scan_charity_removals(path).collect().to_dicts(), [{
                "local_authority_code": "LAD2", "financial_year": 2023,
                "size_category": "Medium", "removals": 1,
            }])

    def test_company_csv_preserves_zeroes_and_filters(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "companies.csv"
            path.write_text(" CompanyNumber,RegAddress.PostCode\n00123456,AB1 2CD\nSC123456,XY1 2ZZ\n")
            with patch.object(core, "COMPANY_HOUSE", path):
                result = core.load_company_house(pl.Series(["00123456"]))
            self.assertEqual(result.to_dicts(), [{
                "CompanyNumber": "00123456", "RegAddress.PostCode": "AB1 2CD",
            }])

    def test_missing_postcode_columns_produce_null(self):
        result = core.charity_address(pl.DataFrame({"id": [1]}))
        self.assertIsNone(result["charity_postcode"][0])

    def test_supported_dates(self):
        values = ["2020-04-01T00:00:00", "2020-04-01", "01/04/2020", "01-04-2020", "2020/04/01", "20200401", "bad", None]
        result = pl.DataFrame({"date": values}).select(core.parse_date_expr("date"))
        self.assertEqual(result.to_series().to_list(), [date(2020, 4, 1)] * 6 + [None, None])

    def test_failed_build_preserves_existing_output(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "register.parquet"
            path.write_bytes(b"previous output")
            def fail_write(frame, destination):
                Path(destination).write_bytes(b"partial output")
                raise OSError("write failed")
            with patch.object(core, "load_charity_register", return_value=pl.DataFrame({"id": [1]})):
                with patch.object(pl.DataFrame, "write_parquet", fail_write):
                    with self.assertRaises(OSError):
                        core.build_charity_register(path)
            self.assertEqual(path.read_bytes(), b"previous output")
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
