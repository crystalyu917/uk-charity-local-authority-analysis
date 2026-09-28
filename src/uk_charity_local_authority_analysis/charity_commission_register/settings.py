"""Read user-facing workflow settings without changing library defaults."""

from datetime import date, datetime
import json
from pathlib import Path

from . import config

CONFIG_PATH = config.PROJECT_ROOT / "config.json"


def load_settings(path: Path = CONFIG_PATH) -> dict:
    settings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("Configuration must be a JSON object")
    unknown = settings.keys() - {"downloads", "build"}
    if unknown:
        raise ValueError(f"Unknown configuration sections: {sorted(unknown)}")
    return settings


def resolve_path(value: str, *, download_date: str | None = None) -> Path:
    """Resolve paths against the repository, independently of the working directory."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Configured paths must be nonempty strings")
    today = date.today().strftime("%d%m%Y")
    path = Path(value.replace("{today}", today).replace("{download_date}", download_date or today))
    return path if path.is_absolute() else config.PROJECT_ROOT / path


def download_settings(settings: dict) -> tuple[dict[str, config.Source], bool]:
    downloads = settings.get("downloads", {})
    if not isinstance(downloads, dict) or downloads.keys() - {"overwrite", "sources"}:
        raise ValueError("downloads accepts only overwrite and sources")
    overwrite = downloads.get("overwrite", True)
    if not isinstance(overwrite, bool):
        raise ValueError("downloads.overwrite must be true or false")
    overrides = downloads.get("sources", {})
    if not isinstance(overrides, dict):
        raise ValueError("downloads.sources must be an object")
    sources = dict(config.DOWNLOAD_SOURCES)
    for name, values in overrides.items():
        if not isinstance(values, dict) or values.keys() - {"url", "directory", "filename"}:
            raise ValueError(f"Invalid download source: {name}")
        previous = sources.get(name)
        merged = dict(zip(("url", "directory", "filename"), previous)) if previous else {}
        merged.update(values)
        if merged.keys() != {"url", "directory", "filename"}:
            raise ValueError(f"Source {name} requires url, directory, and filename")
        url, directory, filename = (merged[key] for key in ("url", "directory", "filename"))
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ValueError(f"Source {name} requires an HTTP(S) URL")
        if not isinstance(filename, str) or not filename or filename in {".", ".."} or any(c in filename for c in "/\\\x00"):
            raise ValueError(f"Source {name} requires a plain filename")
        if not isinstance(directory, (str, Path)):
            raise ValueError(f"Source {name} requires a directory path")
        sources[name] = (url, resolve_path(str(directory)), filename)
    return sources, overwrite


def build_settings(settings: dict, target: str | None = None) -> dict[str, Path | None]:
    build = settings.get("build", {})
    if not isinstance(build, dict) or build.keys() - {"target", "targets"}:
        raise ValueError("build accepts only target and targets")
    target = target if target is not None else build.get("target")
    targets = build.get("targets", {})
    if not isinstance(target, str) or not isinstance(targets, dict) or target not in targets:
        raise ValueError(f"Unknown or missing build target: {target!r}")
    values = targets[target]
    required = {
        "charity_filepath", "classification_filepath", "company_house_filepath",
        "find_that_charity_filepath", "onspd_archive_filepath", "onspd_lookup_filepath",
        "output_path", "utla_directory",
    }
    optional = {"utla_filepath", "onspd_source_csv_filepath"}
    if not isinstance(values, dict) or required - values.keys() or values.keys() - required - optional - {"download_date"}:
        raise ValueError(f"Target {target!r} has missing or unknown path settings")
    download_date = values.get("download_date")
    if download_date is not None:
        if not isinstance(download_date, str) or len(download_date) != 8 or not download_date.isascii() or not download_date.isdigit():
            raise ValueError(f"Target {target!r}: download_date must be a DDMMYYYY string or null")
        try:
            datetime.strptime(download_date, "%d%m%Y")
        except ValueError as error:
            raise ValueError(f"Target {target!r}: download_date must be a valid DDMMYYYY date") from error
    return {
        key: None if key in optional and values.get(key) is None else resolve_path(values[key], download_date=download_date)
        for key in required | optional
    }
