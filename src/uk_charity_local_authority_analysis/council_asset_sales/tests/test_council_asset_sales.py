"""Council configuration and panel integration regressions (no network)."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import polars as pl

from uk_charity_local_authority_analysis.council_asset_sales import config
from uk_charity_local_authority_analysis.council_asset_sales.datasets.la_capital_receipts import datasets
from uk_charity_local_authority_analysis.council_asset_sales.preprocessing import panel


class CouncilAssetSalesTests(unittest.TestCase):
    def test_configured_download_destination_and_endpoint(self):
        with (
            patch.object(config, "COUNCIL_RECEIPTS_PATH", Path("custom/receipts.csv")),
            patch.object(config, "COUNCIL_RECEIPTS_URL", "https://example.org/receipts.csv"),
            patch.object(datasets, "download_file") as download,
        ):
            datasets.download_la_capital_receipts()
            download.assert_called_once_with(
                "https://example.org/receipts.csv",
                dest_dir=Path("custom"), filename="receipts.csv",
            )

    def test_local_register_selection_and_exact_year_lags(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = root / "receipts.csv"
            receipts.write_text(
                "PeriodCode,LA_LGF_Code,ONS_Code,LA_Name,LA_Class,LA_Subclass,Status,EandR1_alltot_rectot\n"
                "201603,1,E06000001,Hartlepool,UA,,submitted,1000\n"
                "201803,1,E06000001,Hartlepool,UA,,submitted,3000\n"
                "201903,1,E06000001,Hartlepool,UA,,submitted,4000\n"
            )
            register = pl.DataFrame({
                "local_authority_code": ["E06000001"],
                "removal_fy": [2018], "size_category": ["Small"],
            })
            old = root / "charity_register_20250101_000000_000000Z.parquet"
            latest = root / "charity_register_20260101_000000_000000Z.parquet"
            register.head(0).write_parquet(old)
            register.write_parquet(latest)
            lookup = root / "postcodes.parquet"
            pl.DataFrame({
                "lad": [{"code": "E06000001", "name": "Hartlepool"}],
                "region": [{"code": "E12000001", "name": "North East"}],
            }).write_parquet(lookup)
            with patch.multiple(
                config, COUNCIL_RAW_DIR=root, COUNCIL_RECEIPTS_PATH=receipts,
                COUNCIL_CHARITY_PATH=None, COUNCIL_POSTCODE_LOOKUP_PATH=lookup,
            ):
                result = panel.load_charity_receipts_panel(start_year=2018, end_year=2019)
                self.assertEqual(result.height, 6)
                row = result.filter(
                    (pl.col("financial_year") == 2018) & (pl.col("size_category") == "Small")
                ).row(0, named=True)
                self.assertEqual(row["removals"], 1)
                self.assertEqual(row["capital_receipts_gbp_millions_lag1"], 3)
                self.assertIsNone(row["capital_receipts_gbp_millions_lag2"])
                self.assertEqual(row["capital_receipts_gbp_millions_lag3"], 1)
                missing = result.filter(pl.col("financial_year") == 2019)
                self.assertEqual(missing["receipt_observed"].to_list(), [False] * 3)
                self.assertEqual(missing["removals"].to_list(), [0] * 3)
                with patch.object(config, "COUNCIL_CHARITY_PATH", old):
                    pinned = panel.load_charity_receipts_panel(start_year=2018, end_year=2018)
                    self.assertEqual(pinned["removals"].sum(), 0)
                with patch.object(config, "COUNCIL_CHARITY_PATH", root / "missing.parquet"):
                    with self.assertRaises(FileNotFoundError):
                        panel.load_charity_receipts_panel(start_year=2018, end_year=2018)


if __name__ == "__main__":
    unittest.main()
