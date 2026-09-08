"""Versioned, validated, and atomic launcher configuration storage."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved application paths for normal, portable, and test environments."""

    data_dir: Path
    local_app_data: Path

    @classmethod
    def for_current_user(cls, data_dir: str | Path | None = None) -> AppPaths:
        resolved_data_dir = Path(
            data_dir
            or os.environ.get("BETTER_TOGETHER_HOME")
            or (Path.home() / ".egs_manager")
        ).expanduser()
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        ).expanduser()
        return cls(
            data_dir=resolved_data_dir.resolve(),
            local_app_data=local_app_data.resolve(),
        )

    @property
    def config_file(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def dbd_template_file(self) -> Path:
        return self.data_dir / "dbd_install.json"

    @property
    def legacy_graphics_preset_dir(self) -> Path:
        return self.data_dir / "graphics_presets"

    @property
    def legendary_executable(self) -> Path:
        return self.data_dir / "legendary.exe"

    @property
    def default_game_settings_file(self) -> Path:
        return (
            self.local_app_data
            / "DeadByDaylight"
            / "Saved"
            / "Config"
            / "EGSClient"
            / "GameUserSettings.ini"
        )


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Replace a text file atomically without exposing a partial write."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    original_mode: int | None = target.stat().st_mode if target.exists() else None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding=encoding, newline="") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        if original_mode is not None and not bool(original_mode & stat.S_IWRITE):
            target.chmod(original_mode | stat.S_IWRITE)
        os.replace(temporary_path, target)
        if original_mode is not None:
            target.chmod(original_mode)
    finally:
        if temporary_path and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def atomic_write_json(path: str | Path, data: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
    )


CONFIG_SCHEMA_VERSION = 3
DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "active": None,
    "account_folder": None,
    "dbd_path": None,
    "game_settings_path": None,
    "input_settings_path": None,
    "launch_arguments": "",
    "presets": {},
    "graphics_presets": {},
    "appearance": {"mode": "dark", "accent": "#CF4C5C"},
}


def _normalize(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return a schema-complete config while preserving future/unknown keys."""

    result = deepcopy(config)
    changed = False
    for key, default in DEFAULT_CONFIG.items():
        if key not in result:
            result[key] = deepcopy(default)
            changed = True

    for key in ("presets", "graphics_presets"):
        if not isinstance(result[key], dict):
            result[key] = {}
            changed = True

    appearance = result.get("appearance")
    if not isinstance(appearance, dict):
        appearance = {}
        changed = True
    normalized_appearance = {
        "mode": appearance.get("mode", "dark"),
        "accent": appearance.get("accent", "#CF4C5C"),
    }
    if normalized_appearance != appearance:
        changed = True
    result["appearance"] = normalized_appearance

    if result.get("schema_version") != CONFIG_SCHEMA_VERSION:
        result["schema_version"] = CONFIG_SCHEMA_VERSION
        changed = True
    return result, changed


class ConfigStore:
    """Owns configuration IO and guarantees same-directory atomic replacement."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            config = deepcopy(DEFAULT_CONFIG)
            self.save(config)
            return config
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfigurationError(
                f"The configuration could not be read: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ConfigurationError("The configuration has an invalid format.")
        config, changed = _normalize(parsed)
        if changed:
            self.save(config)
        return config

    def save(self, config: dict[str, Any]) -> None:
        if not isinstance(config, dict):
            raise ConfigurationError("The configuration has an invalid format.")
        config, _changed = _normalize(config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write_json(self.path, config)
        except OSError as exc:
            raise ConfigurationError(
                f"The configuration could not be saved: {exc}"
            ) from exc
