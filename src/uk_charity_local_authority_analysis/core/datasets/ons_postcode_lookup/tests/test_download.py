"""Offline regression checks for ONS destinations and atomic downloads."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import requests

from uk_charity_local_authority_analysis.core.constants import PROJECT_ROOT
from uk_charity_local_authority_analysis.core.datasets.download import download_file
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup.datasets import (
    DEFAULT_RAW_DIR,
    download_ons_postcode_lookup,
)
from uk_charity_local_authority_analysis.core.datasets.ons_postcode_lookup.endpoint import (
    ONS_POSTCODE_LOOKUP_FILENAME,
)


class OnsDownloadTests(unittest.TestCase):
    def test_destination_is_inside_repository(self):
        self.assertEqual(PROJECT_ROOT, Path(__file__).resolve().parents[6])
        self.assertEqual(DEFAULT_RAW_DIR, PROJECT_ROOT / "data/core/ons/raw")

    @patch("uk_charity_local_authority_analysis.core.datasets.download.requests.get")
    def test_download_and_cache(self, get):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = iter([b"first", b"", b"second"])
        get.return_value = response
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            result = download_ons_postcode_lookup(destination)
            self.assertEqual(result, destination / ONS_POSTCODE_LOOKUP_FILENAME)
            self.assertEqual(result.read_bytes(), b"firstsecond")
            self.assertEqual(download_ons_postcode_lookup(destination), result)
            get.assert_called_once()
            self.assertEqual(list(destination.iterdir()), [result])

    @patch("uk_charity_local_authority_analysis.core.datasets.download.requests.get")
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
                download_ons_postcode_lookup(destination)
            self.assertEqual(list(destination.iterdir()), [])

    @patch("uk_charity_local_authority_analysis.core.datasets.download.requests.get")
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
