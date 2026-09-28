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
            config.DOWNLOAD_SOURCES["onspd"],
            (
                config.ONSPD_POSTCODE_LOOKUP_URL,
                config.DEFAULT_DATA_DIR / "onspd",
                config.ONSPD_POSTCODE_LOOKUP_FILENAME,
            ),
        )
        self.assertEqual(
            config.DOWNLOAD_SOURCES["company_house"],
            (
                config.COMPANY_HOUSE_URL,
                config.DEFAULT_DATA_DIR / "company_house",
                config.COMPANY_HOUSE_FILENAME,
            ),
        )

    def test_script_uses_configured_sources_without_script_edits(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            sources = {"custom": ("https://example.org/new.zip", folder, "new.zip")}
            with (
                patch.object(config, "DOWNLOAD_SOURCES", sources),
                patch.object(download_script.sys, "argv", ["download_and_extract.py", "custom"]),
                patch.object(download_script, "download_file", return_value=folder / "new.zip") as download,
                patch.object(download_script, "extract_zip", return_value=()) as extract,
                patch("builtins.print"),
            ):
                self.assertEqual(download_script.main(), 0)
            download.assert_called_once_with(
                "https://example.org/new.zip",
                dest_dir=folder / download_script.date.today().strftime("%d%m%Y"),
                filename="new.zip", refresh=True,
            )
            extract.assert_called_once_with(folder / "new.zip", refresh=True)

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
