"""Offline checks for JSON overrides and the unified build command."""

from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import build_charity_register as command
from scripts import download_and_extract as download_command
from uk_charity_local_authority_analysis.charity_commission_register import config, settings


class SettingsTests(unittest.TestCase):
    def test_target_date_changes_snapshot_folders_only(self):
        document = settings.load_settings()
        legacy = settings.build_settings(document, "legacy")
        document["build"]["targets"]["latest"]["download_date"] = "28092026"
        paths = settings.build_settings(document, "latest")
        for key in ("charity_filepath", "classification_filepath", "company_house_filepath",
                    "onspd_archive_filepath", "onspd_lookup_filepath"):
            self.assertIn("28092026", paths[key].parts)
            self.assertNotIn("13092026", paths[key].parts)
        self.assertEqual(paths["company_house_filepath"].name, "BasicCompanyDataAsOneFile-2026-09-01.csv")
        self.assertIn("28052025_legacy", str(paths["find_that_charity_filepath"]))
        self.assertEqual(settings.build_settings(document, "legacy"), legacy)

    def test_target_date_is_optional(self):
        document = settings.load_settings()
        target = document["build"]["targets"]["latest"]
        target.pop("download_date")
        for values in (target, {**target, "download_date": None}):
            document["build"]["targets"]["latest"] = values
            path = settings.build_settings(document, "latest")["charity_filepath"]
            self.assertIn(date.today().strftime("%d%m%Y"), path.parts)

    def test_target_date_rejects_invalid_values(self):
        document = settings.load_settings()
        for value in ("31022026", "2026-09-28", "", 28092026, "../data", "1092026"):
            document["build"]["targets"]["latest"]["download_date"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "download_date"):
                settings.build_settings(document, "latest")

    def test_partial_source_override_keeps_other_defaults(self):
        sources, overwrite = settings.download_settings({
            "downloads": {"sources": {"onspd": {"filename": "replacement.zip"}}},
        })
        self.assertTrue(overwrite)
        self.assertEqual(sources["onspd"], (*config.DOWNLOAD_SOURCES["onspd"][:2], "replacement.zip"))
        self.assertEqual(sources["utla"], config.DOWNLOAD_SOURCES["utla"])

    def test_invalid_settings_fail_before_running(self):
        for value in (
            {"overwrite": "false"},
            {"sources": {"new": {"url": "https://example.org/data.zip"}}},
            {"sources": {"onspd": {"filename": "../escape.zip"}}},
            {"overwite": False},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings.download_settings({"downloads": value})
        with self.assertRaises(ValueError):
            settings.build_settings(settings.load_settings(), "missing")

    def test_relative_paths_and_today(self):
        self.assertEqual(
            settings.resolve_path("data/{today}/input.csv"),
            config.PROJECT_ROOT / "data" / date.today().strftime("%d%m%Y") / "input.csv",
        )

    def test_download_overwrite_false_reaches_both_helpers(self):
        with (
            patch.object(download_command, "load_settings", return_value={"downloads": {"overwrite": False}}),
            patch.object(download_command.sys, "argv", ["download", "onspd"]),
            patch.object(download_command, "download_file", return_value=Path("data.zip")) as download,
            patch.object(download_command, "extract_zip", return_value=()) as extract,
            patch("builtins.print"),
        ):
            self.assertEqual(download_command.main(), 0)
        self.assertFalse(download.call_args.kwargs["refresh"])
        extract.assert_called_once_with(Path("data.zip"), refresh=False)

    def test_both_targets_use_the_same_build_with_configured_paths(self):
        document = settings.load_settings()
        for target in ("latest", "legacy"):
            with self.subTest(target=target):
                document["build"]["target"] = target
                paths = settings.build_settings(document)
                with (
                    patch.object(command, "load_settings", return_value=document),
                    patch.object(command.sys, "argv", ["build"]),
                    patch.object(command, "latest_utla_lookup", return_value=Path("utla.csv")) as utla,
                    patch.object(command, "build_onspd_postcode_lookup", return_value=Path("onspd.parquet")) as onspd,
                    patch.object(command, "build_charity_register", return_value=Path("register.parquet")) as build,
                    patch("builtins.print"),
                ):
                    self.assertEqual(command.main(), 0)
                utla.assert_called_once_with(paths["utla_directory"])
                onspd.assert_called_once_with(
                    output_path=paths["onspd_lookup_filepath"],
                    source_csv=paths["onspd_source_csv_filepath"],
                    archive_filepath=paths["onspd_archive_filepath"],
                )
                build.assert_called_once_with(
                    **{key: paths[key] for key in (
                        "output_path", "charity_filepath", "classification_filepath",
                        "company_house_filepath", "find_that_charity_filepath",
                    )},
                    onspd_filepath=Path("onspd.parquet"), utla_filepath=Path("utla.csv"),
                )

    def test_cli_target_override_and_pinned_utla(self):
        document = settings.load_settings()
        document["build"]["targets"]["legacy"]["utla_filepath"] = "data/pinned.csv"
        with (
            patch.object(command, "load_settings", return_value=document),
            patch.object(command.sys, "argv", ["build", "--target", "legacy"]),
            patch.object(command, "latest_utla_lookup") as latest,
            patch.object(command, "build_onspd_postcode_lookup"),
            patch.object(command, "build_charity_register") as build,
            patch("builtins.print"),
        ):
            command.main()
        latest.assert_not_called()
        self.assertEqual(build.call_args.kwargs["utla_filepath"], config.PROJECT_ROOT / "data/pinned.csv")
        self.assertIn("28052025_legacy", str(build.call_args.kwargs["charity_filepath"]))
