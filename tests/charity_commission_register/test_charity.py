"""Integration regressions for the charity snapshot pipeline."""

import unittest
import json
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import polars as pl

from importlib import import_module

core = import_module("uk_charity_local_authority_analysis.charity_commission_register.build_charity_register")
from uk_charity_local_authority_analysis.charity_commission_register import charity_commission, company_house


class CharityPipelineTests(unittest.TestCase):
    def test_csv_and_json_sources_clean_to_equivalent_records(self):
        charities = [{
            "registered_charity_number": 200001,
            "linked_charity_number": 0,
            "charity_company_registration_number": "00123456",
            "date_of_registration": "2020-04-01T00:00:00",
            "date_of_removal": None,
            "charity_has_land": True,
            "latest_income": 25000.5,
        }]
        classifications = [{
            "registered_charity_number": 200001,
            "classification_description": "Makes Grants To Individuals",
        }]
        with TemporaryDirectory() as directory:
            for records, loader, cleaner in (
                (charities, charity_commission.load_charity, charity_commission.clean_charity),
                (classifications, charity_commission.load_charity_classification,
                 charity_commission.clean_charity_classification),
            ):
                csv_path = Path(directory) / "source.csv"
                json_path = Path(directory) / "source.JSON"
                pl.DataFrame(records).write_csv(csv_path)
                # The current public extracts contain a UTF-8 BOM.
                json_path.write_text(json.dumps(records), encoding="utf-8-sig")
                csv_result = cleaner(loader(csv_path))
                json_result = cleaner(loader(json_path)).select(csv_result.columns)
                self.assertTrue(csv_result.equals(json_result))

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
        onspd = pl.DataFrame({
            "pcds": ["SW1A 1AA", "AB1 2CD", "XY1 2ZZ"],
            "lad25cd": ["LAD1", "LAD2", "LAD3"],
        })
        utla = pl.DataFrame({
            "pcds": ["sw1a 1aa", "AB1 2CD"],
            "utla22cd": ["UTLA1", "UTLA2"],
            "utla22nm": ["Authority One", "Authority Two"],
        })
        result = core.load_charity_register(
            charities, classifications, companies, ftc, onspd, utla
        ).sort("registered_charity_number")
        self.assertEqual(result.height, 3)
        self.assertEqual(result["local_authority_code"].to_list(), ["LAD1", "LAD2", "LAD3"])
        self.assertEqual(result["UTLA"].to_list(), ["UTLA1", "UTLA2", None])
        self.assertEqual(result["UTLA_name"].to_list(), ["Authority One", "Authority Two", None])
        with TemporaryDirectory() as directory:
            lookup_path = Path(directory) / "utla.csv"
            utla.write_csv(lookup_path)
            loaded = core.load_charity_register(
                charities, classifications, companies, ftc, onspd, utla_filepath=lookup_path,
            ).sort("registered_charity_number")
            self.assertTrue(loaded.equals(result))
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
            result = company_house.load_company_house(pl.Series(["00123456"]), filepath=path)
            self.assertEqual(result.to_dicts(), [{
                "CompanyNumber": "00123456", "RegAddress.PostCode": "AB1 2CD",
            }])

    def test_missing_postcode_columns_produce_null(self):
        result = core.charity_address(pl.DataFrame({"id": [1]}))
        self.assertIsNone(result["charity_postcode"][0])

    def test_company_csv_fallback_validates_required_records(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "companies.csv"
            path.write_text(
                ' CompanyNumber,RegAddress.PostCode\n'
                '00123456,"AB1 2CD"\nSC123456,XY1 2ZZ,extra\n'
            )
            result = company_house.load_company_house(pl.Series(["00123456"]), filepath=path)
            self.assertEqual(result.to_dicts(), [{
                "CompanyNumber": "00123456", "RegAddress.PostCode": "AB1 2CD",
            }])
            with self.assertRaisesRegex(ValueError, "SC123456.*expected 2 fields, found 3"):
                company_house.load_company_house(pl.Series(["SC123456"]), filepath=path)

    def test_supported_dates(self):
        values = ["2020-04-01T00:00:00", "2020-04-01", "01/04/2020", "01-04-2020", "2020/04/01", "20200401", "bad", None]
        result = pl.DataFrame({"date": values}).select(charity_commission.parse_date_expr("date"))
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

    def test_runs_preserve_history_even_with_identical_timestamps(self):
        with TemporaryDirectory() as directory:
            base = Path(directory) / "register.parquet"
            base.write_bytes(b"old register")
            data = pl.DataFrame({
                "local_authority_code": ["LAD1"], "removal_fy": [2024],
                "size_category": ["Small"],
            })
            with patch.object(core, "datetime") as clock:
                clock.now.return_value = datetime(2026, 9, 6, 14, 30, 25, 123456, tzinfo=timezone.utc)
                with patch.object(core, "load_charity_register", return_value=data):
                    first = core.build_charity_register(base)
                    second = core.build_charity_register(base)
            self.assertEqual(first.name, "register_20260906_143025_123456Z.parquet")
            self.assertEqual(second.name, "register_20260906_143025_123457Z.parquet")
            self.assertTrue(pl.read_parquet(first).equals(data))
            self.assertTrue(pl.read_parquet(second).equals(data))
            self.assertEqual(base.read_bytes(), b"old register")
            record = json.loads(second.with_suffix(".run.json").read_text())
            self.assertEqual(record["output"]["path"], str(second.resolve()))
            self.assertEqual(record["output"]["rows"], 1)
            self.assertEqual(record["output"]["size_bytes"], second.stat().st_size)
            self.assertEqual(record["inputs"]["charity_commission"]["path"], str(core.CHARITY_FILEPATH.resolve()))
            self.assertEqual(
                record["onspd"]["path"], str(core.ONSPD_LOOKUP_FILEPATH.resolve())
            )
            self.assertTrue(first.with_suffix(".run.json").is_file())
            self.assertEqual(core.latest_charity_register(base), second)
            with patch.object(core, "CHARITY_REGISTER_FILEPATH", base):
                self.assertEqual(core.scan_charity_removals().collect()["removals"][0], 1)

    def test_latest_run_falls_back_and_reports_missing_output(self):
        with TemporaryDirectory() as directory:
            base = Path(directory) / "register.parquet"
            with self.assertRaises(FileNotFoundError):
                core.latest_charity_register(base)
            base.write_bytes(b"old register")
            self.assertEqual(core.latest_charity_register(base), base)

    def test_record_failure_does_not_leave_unrecorded_output(self):
        with TemporaryDirectory() as directory:
            base = Path(directory) / "register.parquet"
            real_link = core.os.link
            def link(source, destination):
                if str(destination).endswith(".run.json"):
                    raise OSError("record publication failed")
                return real_link(source, destination)
            with patch.object(core, "load_charity_register", return_value=pl.DataFrame({"id": [1]})):
                with patch.object(core.os, "link", side_effect=link):
                    with self.assertRaises(OSError):
                        core.build_charity_register(base)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
