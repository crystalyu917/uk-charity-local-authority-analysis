"""Exercise the single command and its shared analysis contract on small sources."""

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import polars as pl

from charity_lease.cli.run_charity_pipeline import main
from charity_lease.data import (
    PROJECT_DIR, boolean_flag, completed_runs, latest_register, latest_property_input,
    read_output, validate_charity_numbers,
)
from charity_lease.pipeline.lease_terms import eligible_registered_lease


class PipelineWorkflowTests(unittest.TestCase):
    def test_automatic_property_selection_uses_source_month_and_reports_missing(self):
        with TemporaryDirectory(dir=PROJECT_DIR, prefix=".test-inputs-") as folder:
            root = Path(folder)
            for name in ("CCOD_FULL_2026_10.csv", "CCOD_FULL_2025_12.csv", "CCOD_FULL_2026_13.csv",
                         "LEASES_FULL_2026_09.csv", "LEASES_FULL_2026_08.csv", "LEASES_FULL_2026_00.csv"):
                (root / name).touch()
            self.assertEqual(latest_property_input("ccod", root).name, "CCOD_FULL_2026_10.csv")
            self.assertEqual(latest_property_input("lease", root).name, "LEASES_FULL_2026_09.csv")
            empty = root / "empty"
            empty.mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "--leases-input"):
                latest_property_input("lease", empty)

    def test_automatic_register_selection_prefers_timestamp_to_fallback(self):
        with TemporaryDirectory(dir=PROJECT_DIR, prefix=".test-registers-") as folder:
            root = Path(folder)
            fallback = root / "charity_register.parquet"
            fallback.touch()
            self.assertEqual(latest_register(root), fallback)
            for name in ("charity_register_20261002_000000_000000Z.parquet",
                         "charity_register_20261001_000000_000000Z.parquet", "unrelated.parquet"):
                (root / name).touch()
            self.assertEqual(latest_register(root).name, "charity_register_20261002_000000_000000Z.parquet")

    def test_command_retains_overlap_and_suppresses_freeholder_terms(self):
        with TemporaryDirectory(dir=PROJECT_DIR, prefix=".test-workflow-") as folder:
            root = Path(folder)
            register = pl.DataFrame({
                "registered_charity_number": [1, 2, 3],
                "charity_name": ["Helping Hands Trust", "Other Charity", "Removed Charity"],
                "registered_address": ["10 Test Road", "20 Test Road", "30 Test Road"],
                "registered_postcode": ["SW1A 1AA"] * 3,
                "date_of_removal": [None, None, "2020-01-01"],
            })
            register.write_parquet(root / "register.parquet")
            with (root / "ccod.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Property Address", "Postcode", "Tenure", "Proprietor Name (4)", "Company Registration No. (1)"])
                writer.writerow(["10 Test Road", "SW1A 1AA", "Freehold", "Helping Hands Trust", "00123456"])
                writer.writerow(["20 Test Road", "SW1A 1AA", "Freehold", "Unrelated Estates", "00999999"])
            with (root / "leases.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Unique Identifier", "Associated Property Description", "Date of Lease", "Term"])
                for number in (10, 20):
                    writer.writerow([f"L{number}", f"{number} Test Road SW1A 1AA", "2020-01-01", "99 years from 1 January 2000"])
            common = ["charity-lease-match", "--charity-input", str(root / "register.parquet"),
                      "--ccod-input", str(root / "ccod.csv"), "--leases-input", str(root / "leases.csv"),
                      "--as-of", "2026-10-10"]
            outputs = []
            for format in ("parquet", "csv"):
                folder = root / format
                with patch("sys.argv", common + ["--output-dir", str(folder), "--format", format]):
                    main()
                paths = completed_runs(folder)
                self.assertEqual(len(paths), 1)
                frame = read_output(paths[0])
                validate_charity_numbers(frame, unique=True)
                frame = frame.with_columns([
                    boolean_flag(c).alias(c) for c in ("ccod_matched", "registered_lease_matched", "charity_is_freeholder")
                ])
                self.assertEqual(frame.height, 2)
                self.assertTrue(frame["ccod_matched"].all())
                self.assertTrue(frame["registered_lease_matched"].all())
                self.assertEqual(frame["lease_status"].to_list(), ["freehold", "leasehold"])
                self.assertEqual(frame["ccod_company_registration_no_1"].to_list(), ["00123456", "00999999"])
                self.assertIsNone(frame["lease_years_remaining"][0])
                self.assertIsNotNone(frame["lease_years_remaining"][1])
                self.assertEqual(frame.select(eligible_registered_lease())["registered_lease_matched"].to_list(), [False, True])
                outputs.append(frame)
            self.assertEqual(outputs[0]["lease_status"].to_list(), outputs[1]["lease_status"].to_list())

    def test_missing_identifiers_fail_before_deduplication(self):
        with self.assertRaisesRegex(ValueError, "nonmissing"):
            validate_charity_numbers(pl.DataFrame({"registered_charity_number": [None, None]}, schema={"registered_charity_number": pl.String}))

    def test_completed_runs_prefer_parquet_within_a_timestamp(self):
        with TemporaryDirectory(dir=PROJECT_DIR, prefix=".test-runs-") as folder:
            root = Path(folder)
            for timestamp in ("20261001_000000_000000Z", "20261002_000000_000000Z"):
                run = root / timestamp
                run.mkdir()
                for extension in ("parquet", "csv"):
                    (run / f"charity_register_with_property.{extension}").touch()
            self.assertEqual([p.suffix for p in completed_runs(root)], [".parquet", ".parquet"])
            self.assertEqual(completed_runs(root)[-1].parent.name, "20261002_000000_000000Z")


if __name__ == "__main__":
    unittest.main()
