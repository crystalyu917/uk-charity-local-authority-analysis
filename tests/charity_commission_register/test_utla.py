"""UTLA matching and dated source selection regressions."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import polars as pl

from uk_charity_local_authority_analysis.charity_commission_register.config import UTLA_CSV_FILENAME
from uk_charity_local_authority_analysis.charity_commission_register.utla import (
    add_utla, latest_utla_lookup, load_utla,
)


class UtlaTests(unittest.TestCase):
    def test_matching_preserves_rows_and_columns_and_deduplicates_mappings(self):
        charities = pl.DataFrame({
            "id": [4, 1, 1, 2, 3],
            "charity_postcode": [" ab1\t2Cd ", "AB12CD", "unknown", None, ""],
            "local_authority_code": ["LAD"] * 5,
        })
        lookup = pl.DataFrame({
            "pcds": ["AB1 2CD", "ab12cd", None, "  "],
            "utla22cd": ["U1", "U1", "BAD", "BAD"],
            "utla22nm": ["Authority", "Authority", "Bad", "Bad"],
        })
        result = add_utla(charities, lookup)
        self.assertTrue(result.select(charities.columns).equals(charities))
        self.assertEqual(result.columns, charities.columns + ["UTLA", "UTLA_name"])
        self.assertEqual(result["UTLA"].to_list(), ["U1", "U1", None, None, None])
        self.assertEqual(result["UTLA_name"].to_list(), ["Authority", "Authority", None, None, None])

    def test_conflicting_codes_or_names_fail_validation(self):
        charities = pl.DataFrame({"charity_postcode": ["AB12CD"]})
        for codes, names in ((["U1", "U2"], ["One", "Two"]), (["U1", "U1"], ["One", "Other"])):
            with self.subTest(codes=codes, names=names):
                lookup = pl.DataFrame({"pcds": ["AB1 2CD", "ab12cd"], "utla22cd": codes, "utla22nm": names})
                with self.assertRaises(pl.exceptions.ComputeError):
                    add_utla(charities, lookup)

    def test_latest_lookup_uses_calendar_date_and_nested_csv(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, "scripts/download_and_extract.py utla"):
                latest_utla_lookup(root)
            for folder in ("31012026", "01022026", "02022026_legacy", "31022026"):
                path = root / folder / "archive" / UTLA_CSV_FILENAME
                path.parent.mkdir(parents=True)
                path.write_text("pcds,utla22cd,utla22nm,unused\nAB1 2CD,U1,Authority,x\n")
            selected = latest_utla_lookup(root)
            self.assertEqual(selected, root / "01022026" / "archive" / UTLA_CSV_FILENAME)
            self.assertEqual(load_utla(selected).columns, ["pcds", "utla22cd", "utla22nm"])
            (root / "01022026" / UTLA_CSV_FILENAME).write_bytes(selected.read_bytes())
            with self.assertRaisesRegex(ValueError, "Multiple UTLA CSVs"):
                latest_utla_lookup(root)

    def test_missing_explicit_lookup_and_existing_utla_columns_fail(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "scripts/download_and_extract.py utla"):
                load_utla(Path(directory) / "missing.csv")
        with self.assertRaisesRegex(ValueError, "already has UTLA"):
            add_utla(pl.DataFrame({"charity_postcode": ["AB12CD"], "UTLA": ["U1"]}), pl.DataFrame())
