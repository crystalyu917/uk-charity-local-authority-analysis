"""Offline checks for the two source archives and their extraction."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from uk_charity_local_authority_analysis.charity_commission_register import charity_commission as datasets


class CharityCommissionExtractionTests(unittest.TestCase):
    def test_missing_archive_reports_error_without_creating_output(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, "archive not found"):
                datasets.extract_charity_commission(
                    charity_archive_filepath=root / "missing.zip",
                    classification_archive_filepath=root / "classification.zip",
                )
            self.assertEqual(list(root.iterdir()), [])

    def test_explicit_archive_and_output_filepaths(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            charity_archive = root / "charity.zip"
            classification_archive = root / "classification.zip"
            for archive_path in (charity_archive, classification_archive):
                with ZipFile(archive_path, "w") as archive:
                    archive.writestr("original.json", "[]")
            charity_output = root / "custom" / "charity.json"
            classification_output = root / "another" / "classification.json"
            files = datasets.extract_charity_commission(
                charity_archive_filepath=charity_archive,
                classification_archive_filepath=classification_archive,
                charity_output_filepath=charity_output,
                classification_output_filepath=classification_output,
            )
            self.assertEqual(files.charity, charity_output)
            self.assertEqual(files.classification, classification_output)
            self.assertEqual(charity_output.read_text(), "[]")
            self.assertEqual(classification_output.read_text(), "[]")
            self.assertTrue(charity_archive.is_file())
            self.assertTrue(classification_archive.is_file())

    def test_cached_archives_extract_both_sources_and_repair_partial_files(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            payload = b'[{"registered_charity_number":123456}]'
            for filename in (
                datasets.CHARITY_COMMISSION_CHARITY_ARCHIVE_FILEPATH.name,
                datasets.CHARITY_COMMISSION_CLASSIFICATION_ARCHIVE_FILEPATH.name,
            ):
                with ZipFile(destination / filename, "w") as archive:
                    archive.writestr(Path(filename).stem + ".json", payload)
            files = datasets.extract_charity_commission(destination)
            self.assertNotEqual(files.charity, files.classification)
            for path in (files.charity, files.classification):
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(path.parent.parent, destination)
            modified = files.charity.stat().st_mtime_ns
            datasets.extract_charity_commission(destination)
            self.assertEqual(files.charity.stat().st_mtime_ns, modified)
            files.classification.write_bytes(b"partial")
            datasets.extract_charity_commission(destination)
            self.assertEqual(files.classification.read_bytes(), payload)

    def test_rejects_unsafe_or_ambiguous_archive(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            charity = destination / "charity.zip"
            files = datasets.CharityCommissionFiles(charity, destination / "classification.zip")
            with ZipFile(files.classification, "w") as archive:
                archive.writestr("classification.json", "[]")
            for members in (("../outside.json",), ("one.json", "two.json")):
                with self.subTest(members=members):
                    with ZipFile(charity, "w") as archive:
                        for member in members:
                            archive.writestr(member, "[]")
                    with self.assertRaises(ValueError):
                        datasets.extract_charity_commission(
                            charity_archive_filepath=charity,
                            classification_archive_filepath=files.classification,
                        )
                    self.assertFalse((destination / "outside.json").exists())


if __name__ == "__main__":
    unittest.main()
