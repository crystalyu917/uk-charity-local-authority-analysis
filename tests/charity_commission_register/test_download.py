"""Offline regression checks for the shared download module."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import requests

from scripts import download_and_extract as download_script
from uk_charity_local_authority_analysis.charity_commission_register import config, filepath
from uk_charity_local_authority_analysis.charity_commission_register.download_and_extract import download_file


class DownloadTests(unittest.TestCase):
    def test_script_sources_use_library_defaults(self):
        self.assertEqual(
            download_script.DEFAULT_SOURCES["onspd"],
            (
                config.ONSPD_POSTCODE_LOOKUP_URL,
                download_script.DATA_DIR / "onspd",
                config.ONSPD_POSTCODE_LOOKUP_FILENAME,
            ),
        )
        self.assertEqual(
            download_script.DEFAULT_SOURCES["company_house"],
            (
                config.COMPANY_HOUSE_URL,
                download_script.DATA_DIR / "company_house",
                config.COMPANY_HOUSE_FILENAME,
            ),
        )

    def test_script_source_overrides_replace_defaults_and_add_sources(self):
        defaults = {
            "existing": ("https://example.org/old.zip", Path("old"), "old.zip"),
            "unchanged": ("https://example.org/same.zip", Path("same"), "same.zip"),
        }
        overrides = {
            "existing": ("https://example.org/new.zip", Path("new"), "new.zip"),
            "additional": ("https://example.org/extra.zip", Path("extra"), "extra.zip"),
        }

        sources = download_script.resolve_sources(defaults, overrides)

        self.assertEqual(sources["existing"], overrides["existing"])
        self.assertEqual(sources["additional"], overrides["additional"])
        self.assertEqual(sources["unchanged"], defaults["unchanged"])
        self.assertEqual(defaults["existing"][2], "old.zip")

    def test_filepath_defaults_use_config_filenames(self):
        self.assertEqual(filepath.ONSPD_ARCHIVE_FILEPATH.name, config.ONSPD_POSTCODE_LOOKUP_FILENAME)
        self.assertEqual(filepath.UTLA_ARCHIVE_FILEPATH.name, config.UTLA_ARCHIVE_FILENAME)

    @patch("uk_charity_local_authority_analysis.charity_commission_register.download_and_extract.requests.get")
    def test_download_and_cache(self, get):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = iter([b"first", b"", b"second"])
        get.return_value = response
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            result = download_file("https://example.org/archive.zip", destination)
            self.assertEqual(result, destination / "archive.zip")
            self.assertEqual(result.read_bytes(), b"firstsecond")
            self.assertEqual(download_file("https://example.org/archive.zip", destination), result)
            get.assert_called_once()
            self.assertEqual(list(destination.iterdir()), [result])

    @patch("uk_charity_local_authority_analysis.charity_commission_register.download_and_extract.requests.get")
    def test_interrupted_download_is_not_cached(self, get):
        def interrupted_chunks(*, chunk_size):
            yield b"partial"
            raise requests.ConnectionError("connection interrupted")

        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.side_effect = interrupted_chunks
        get.return_value = response
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            with self.assertRaises(requests.ConnectionError):
                download_file("https://example.org/archive.zip", destination)
            self.assertEqual(list(destination.iterdir()), [])

    @patch("uk_charity_local_authority_analysis.charity_commission_register.download_and_extract.requests.get")
    def test_http_error_is_not_cached(self, get):
        response = MagicMock()
        response.__enter__.return_value = response
        response.raise_for_status.side_effect = requests.HTTPError("404")
        get.return_value = response
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            with self.assertRaises(requests.HTTPError):
                download_file("https://example.org/missing.zip", destination)
            self.assertEqual(list(destination.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
