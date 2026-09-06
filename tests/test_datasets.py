"""Exercise archive extraction and the ONS pipeline without network access."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

import polars as pl

from uk_charity_local_authority_analysis.core.datasets.extraction import (
    extract_single_file_zip, extract_zip_members,
)
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup import datasets as ons


class DatasetTests(unittest.TestCase):
    def test_archive_lookup_joins_names_and_reuses_extraction(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            archive_path = destination / ons.ONS_POSTCODE_LOOKUP_FILENAME
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("Data/ONSPD_MAY_2026_UK.csv", "pcds,lad25cd,rgn25cd\nSW1A 1AA,E09000033,E12000007\nAB1 2CD,X,Y\n")
                archive.writestr("Documents/LAD Local Authority District names and codes UK test.csv", "LAD25CD,LAD25NM\nE09000033,Westminster\n")
                archive.writestr("Documents/RGN Region names and codes EN test.csv", "RGN25CD,RGN25NM\nE12000007,London\n")
                archive.writestr("unused.txt", "do not extract")
            with patch("uk_charity_local_authority_analysis.core.datasets.download.requests.get") as get:
                result = ons.load_ons_postcode_lookup(destination)
                files = ons.extract_ons_postcode_lookup(destination)
                before = files.postcode.stat().st_mtime_ns
                ons.extract_ons_postcode_lookup(destination)
                self.assertEqual(files.postcode.stat().st_mtime_ns, before)
                get.assert_not_called()
            self.assertEqual(result.schema, ons.ONS_POSTCODE_LOOKUP_SCHEMA)
            self.assertEqual(result["lad"][0], {"code": "E09000033", "name": "Westminster"})
            self.assertEqual(result["region"][0], {"code": "E12000007", "name": "London"})
            self.assertEqual(result["lad"][1], {"code": "X", "name": None})
            self.assertFalse((destination / archive_path.stem / "unused.txt").exists())

    def test_standalone_build_and_failed_rebuild(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            output = root / "lookup.parquet"
            source.write_text("pcds,lad25cd,rgn25cd\nSW1A 1AA,E09000033,E12000007\n")
            ons.build_ons_postcode_lookup(output, source)
            self.assertEqual(pl.read_parquet(output)["lad"][0], {"code": "E09000033", "name": None})
            previous = output.read_bytes()
            def fail_write(frame, path):
                Path(path).write_bytes(b"partial")
                raise OSError("write failed")
            with patch.object(pl.LazyFrame, "sink_parquet", fail_write):
                with self.assertRaises(OSError):
                    ons.build_ons_postcode_lookup(output, source)
            self.assertEqual(output.read_bytes(), previous)

    def test_single_file_extraction_repairs_truncated_cache(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "single.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("data.csv", "a,b\n1,2\n")
            output = extract_single_file_zip(archive_path, root)
            output.write_text("partial")
            self.assertEqual(extract_single_file_zip(archive_path, root).read_text(), "a,b\n1,2\n")

    def test_extraction_rejects_unsafe_or_missing_members(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "members.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("data.csv", "a,b\n")
            for name in ("../outside.csv", "C:/outside.csv", "folder/CON", "missing.csv"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    extract_zip_members(archive_path, [name], root)


if __name__ == "__main__":
    unittest.main()
