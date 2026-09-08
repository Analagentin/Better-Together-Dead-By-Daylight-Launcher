import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .config import AppPaths, ConfigStore, atomic_write_json, atomic_write_text
from .constants import (
    DBD_APP_NAME,
    DBD_EXECUTABLE,
    EAC_SPLASH_RELATIVE,
    GAME_SETTINGS_SECTION,
    INPUT_SETTINGS_SECTION,
    MOUSE_KEYS,
    QUALITY_KEYS,
    SCALABILITY_SECTION,
)
from .errors import ManagerError
from .settings_data import DEFAULT_AXIS_MAPPINGS, parse_values, update_values

try:
    from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
except ImportError:  # The packaged build includes Pillow via requirements.txt.
    Image = ImageDraw = ImageFont = PngImagePlugin = None


_SAFE_NAME_PATTERN = re.compile(r"[\w .-]+", flags=re.UNICODE)


class EGSManager:
    def __init__(self, paths=None):
        self.paths = paths or AppPaths.for_current_user()
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self._config_store = ConfigStore(self.paths.config_file)
        self.config = self._load_config()
        self._migrate_graphics_presets_to_files()
        if not self.config.get("dbd_path"):
            self._migrate_existing_dbd_path()

    def _load_config(self):
        return self._config_store.load()

    def _write_config(self, config=None):
        data = self.config if config is None else config
        self._config_store.save(data)

    @staticmethod
    def _validate_name(name, label):
        name = name.strip()
        if not name:
            raise ManagerError(f"Please enter a {label} name.")
        if not _SAFE_NAME_PATTERN.fullmatch(name):
            raise ManagerError(f"The {label} name contains invalid characters.")
        if name in {".", ".."}:
            raise ManagerError(f"This {label} name is not allowed.")
        return name

    @classmethod
    def validate_account_name(cls, name):
        return cls._validate_name(name, "profile")

    @classmethod
    def validate_graphics_preset_name(cls, name):
        return cls._validate_name(name, "graphics preset")

    @classmethod
    def validate_launch_preset_name(cls, name):
        return cls._validate_name(name, "preset")

    def account_path(self, name):
        account_folder = self.account_folder
        if not account_folder:
            raise ManagerError("Please select an account folder first.")
        return account_folder / self.validate_account_name(name)

    def accounts(self):
        account_folder = self.account_folder
        if not account_folder or not account_folder.is_dir():
            return []
        return sorted(
            (path.name for path in account_folder.iterdir() if path.is_dir()),
            key=str.casefold,
        )

    @property
    def active(self):
        return self.config.get("active")

    @property
    def account_folder(self):
        value = self.config.get("account_folder")
        return Path(value) if value else None

    @property
    def dbd_path(self):
        value = self.config.get("dbd_path")
        return Path(value) if value else None

    @property
    def game_settings_path(self):
        value = self.config.get("game_settings_path")
        return Path(value) if value else self.default_game_settings_file()

    @property
    def input_settings_path(self):
        value = self.config.get("input_settings_path")
        return Path(value) if value else self.default_input_settings_file()

    def appearance(self):
        appearance = self.config.get("appearance", {})
        if not isinstance(appearance, dict):
            appearance = {}
        mode = appearance.get("mode")
        if mode not in {"dark", "light"}:
            mode = "dark"
        accent = str(appearance.get("accent", "")).strip().upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", accent):
            accent = "#CF4C5C"
        return {"mode": mode, "accent": accent}

    def set_appearance(self, mode, accent):
        if mode not in {"dark", "light"}:
            raise ManagerError("The appearance mode must be dark or light.")
        accent = str(accent).strip().upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", accent):
            raise ManagerError("The accent color must be a six-digit hex color.")
        self.config["appearance"] = {"mode": mode, "accent": accent}
        self._write_config()
        return dict(self.config["appearance"])

    def launch_arguments(self):
        """Return saved game arguments as a display-ready command line."""

        value = self.config.get("launch_arguments", "")
        return value if isinstance(value, str) else ""

    def set_launch_arguments(self, arguments):
        """Validate and persist optional arguments passed through to DBD."""

        arguments = str(arguments).strip()
        try:
            self.parse_launch_arguments(arguments)
        except ValueError as exc:
            raise ManagerError(
                "Launch arguments contain an unmatched quotation mark."
            ) from exc
        self.config["launch_arguments"] = arguments
        self._write_config()
        return arguments

    @staticmethod
    def parse_launch_arguments(arguments):
        """Split Windows-style user input into arguments for subprocess."""

        if not arguments.strip():
            return []
        parsed = shlex.split(arguments, posix=False)
        # shlex's Windows-like mode retains enclosing quotes. Popen receives a
        # sequence and applies Windows quoting itself, so remove them here.
        return [
            argument[1:-1]
            if len(argument) >= 2
            and argument.startswith(('"', "'"))
            and argument.endswith(('"', "'"))
            else argument
            for argument in parsed
        ]

    def set_game_settings_path(self, path):
        settings_file = Path(path).expanduser().resolve()
        if not settings_file.is_file():
            raise ManagerError(
                f"GameUserSettings.ini was not found at '{settings_file}'."
            )
        if settings_file.suffix.casefold() != ".ini":
            raise ManagerError("Please select a GameUserSettings.ini file.")
        self.config["game_settings_path"] = str(settings_file)
        self._write_config()
        return settings_file

    def set_input_settings_path(self, path):
        input_file = Path(path).expanduser().resolve()
        if not input_file.is_file():
            raise ManagerError(f"Input.ini was not found at '{input_file}'.")
        if input_file.name.casefold() != "input.ini":
            raise ManagerError("Please select an Input.ini file.")
        self.config["input_settings_path"] = str(input_file)
        self._write_config()
        return input_file

    def set_account_folder(self, path):
        account_folder = Path(path).expanduser().resolve()
        account_folder.mkdir(parents=True, exist_ok=True)
        if not account_folder.is_dir():
            raise ManagerError("The selected account folder is not a directory.")
        self.config["account_folder"] = str(account_folder)
        if self.active not in {
            item.name for item in account_folder.iterdir() if item.is_dir()
        }:
            self.config["active"] = None
        self._write_config()
        return account_folder

    def presets(self):
        presets = self.config.get("presets", {})
        return presets if isinstance(presets, dict) else {}

    def graphics_presets(self):
        presets = {}
        preset_dir = self.graphics_preset_dir()
        if not preset_dir.is_dir():
            return presets
        prefix = f"{self.game_settings_path.name}-"
        for preset_file in preset_dir.glob(f"{self.game_settings_path.name}-*"):
            name = preset_file.name.removeprefix(prefix)
            if not name:
                continue
            try:
                text = preset_file.read_text(encoding="utf-8-sig")
                values = self._parse_ini_values(text)
                presets[name] = self._graphics_settings_from_values(values)
            except (OSError, ManagerError):
                continue
        return presets

    def save_graphics_preset(self, name, settings):
        name = self.validate_graphics_preset_name(name)
        preset_file = self.graphics_preset_path(name)
        self.save_game_settings(
            self.game_settings_path,
            settings,
            create_backup=False,
            destination=preset_file,
        )
        return name

    def delete_graphics_preset(self, name):
        name = self.validate_graphics_preset_name(name)
        preset_file = self.graphics_preset_path(name)
        if not preset_file.is_file():
            raise ManagerError(f"The graphics preset '{name}' was not found.")
        try:
            preset_file.unlink()
        except OSError as exc:
            raise ManagerError(
                f"The graphics preset could not be deleted: {exc}"
            ) from exc
        legacy_presets = self.config.get("graphics_presets")
        if isinstance(legacy_presets, dict) and name in legacy_presets:
            del legacy_presets[name]
            self.config["graphics_presets"] = legacy_presets
            self._write_config()

    def save_preset(self, name, entries, delay_seconds):
        name = self.validate_launch_preset_name(name)

        available = set(self.accounts())
        normalized_entries = []
        seen_accounts = set()
        for entry in entries:
            if isinstance(entry, str):
                account = entry
                graphics_preset = None
                input_preset = None
            elif isinstance(entry, dict):
                account = entry.get("account")
                graphics_preset = entry.get("graphics_preset") or None
                input_preset = entry.get("input_preset") or None
            else:
                raise ManagerError("The launch preset contains an invalid profile.")
            if account and account not in seen_accounts:
                normalized_entries.append(
                    {
                        "account": account,
                        "graphics_preset": graphics_preset,
                        "input_preset": input_preset,
                    }
                )
                seen_accounts.add(account)

        if not normalized_entries:
            raise ManagerError("Select at least one profile for the preset.")
        missing = [
            entry["account"]
            for entry in normalized_entries
            if entry["account"] not in available
        ]
        if missing:
            raise ManagerError(
                "These profiles are not available: " + ", ".join(missing)
            )
        available_graphics = set(self.graphics_presets())
        missing_graphics = [
            entry["graphics_preset"]
            for entry in normalized_entries
            if entry["graphics_preset"]
            and entry["graphics_preset"] not in available_graphics
        ]
        if missing_graphics:
            raise ManagerError(
                "These graphics presets are not available: "
                + ", ".join(dict.fromkeys(missing_graphics))
            )
        available_inputs = set(self.input_presets())
        missing_inputs = [
            entry["input_preset"]
            for entry in normalized_entries
            if entry["input_preset"] and entry["input_preset"] not in available_inputs
        ]
        if missing_inputs:
            raise ManagerError(
                "These input presets are not available: "
                + ", ".join(dict.fromkeys(missing_inputs))
            )
        try:
            delay_seconds = int(delay_seconds)
        except (TypeError, ValueError) as exc:
            raise ManagerError("The launch delay must be a whole number.") from exc
        if not 0 <= delay_seconds <= 3600:
            raise ManagerError("The launch delay must be between 0 and 3600 seconds.")

        presets = dict(self.presets())
        presets[name] = {
            "entries": normalized_entries,
            "delay_seconds": delay_seconds,
        }
        self.config["presets"] = presets
        self._write_config()
        return name

    def delete_preset(self, name):
        presets = dict(self.presets())
        if name not in presets:
            raise ManagerError(f"The preset '{name}' was not found.")
        del presets[name]
        self.config["presets"] = presets
        self._write_config()

    def default_game_settings_file(self):
        return self.paths.default_game_settings_file

    def default_input_settings_file(self):
        return self.game_settings_path.resolve().parent / "Input.ini"

    @staticmethod
    def _parse_ini_values(text):
        return parse_values(text)

    @staticmethod
    def _parse_mapping_payload(payload):
        values = {}
        for part in re.finditer(r'(\w+)=(?:"([^"]*)"|([^,()]+))', payload):
            values[part.group(1)] = (
                part.group(2) if part.group(2) is not None else part.group(3)
            )
        return values

    @staticmethod
    def _format_action_mapping(action, mapping):
        if isinstance(mapping, str):
            mapping = {"key": mapping}
        key = str(mapping.get("key", "")).strip()

        def bool_text(value):
            return "True" if bool(value) else "False"

        return (
            f'ActionMappings=(ActionName="{action}",'
            f"bShift={bool_text(mapping.get('shift'))},"
            f"bCtrl={bool_text(mapping.get('ctrl'))},"
            f"bAlt={bool_text(mapping.get('alt'))},"
            f"bCmd={bool_text(mapping.get('cmd'))},Key={key})"
        )

    @staticmethod
    def _format_axis_mapping(axis, mapping):
        key = str(mapping.get("key", "")).strip()
        scale = float(mapping.get("scale", 1.0))
        return f'AxisMappings=(AxisName="{axis}",Scale={scale:.6f},Key={key})'

    @staticmethod
    def _device_for_key(key):
        if key in MOUSE_KEYS or key.startswith("Mouse"):
            return "mouse"
        if key.startswith("Gamepad_"):
            return "controller"
        if key:
            return "keyboard"
        return None

    def read_input_settings(self, path=None):
        input_file = Path(path or self.input_settings_path).resolve()
        if not input_file.is_file():
            raise ManagerError(f"Input.ini was not found at '{input_file}'.")
        try:
            text = input_file.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ManagerError(f"The input settings could not be read: {exc}") from exc

        actions = {}
        action_mappings = {}
        axis_mappings = {}
        section = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if section != INPUT_SETTINGS_SECTION:
                continue
            if line.startswith("ActionMappings=(") and line.endswith(")"):
                values = self._parse_mapping_payload(
                    line.removeprefix("ActionMappings=(").removesuffix(")")
                )
                action = values.get("ActionName")
                key = values.get("Key")
                if action and key:
                    actions.setdefault(action, []).append(key)
                    action_mappings.setdefault(action, []).append(
                        {
                            "key": key,
                            "shift": values.get("bShift", "False").casefold() == "true",
                            "ctrl": values.get("bCtrl", "False").casefold() == "true",
                            "alt": values.get("bAlt", "False").casefold() == "true",
                            "cmd": values.get("bCmd", "False").casefold() == "true",
                        }
                    )
            elif line.startswith("AxisMappings=(") and line.endswith(")"):
                values = self._parse_mapping_payload(
                    line.removeprefix("AxisMappings=(").removesuffix(")")
                )
                axis = values.get("AxisName")
                key = values.get("Key")
                try:
                    scale = float(values.get("Scale", "1"))
                except ValueError:
                    continue
                if axis and key:
                    axis_mappings.setdefault(axis, []).append(
                        {"key": key, "scale": scale}
                    )
        if not actions:
            raise ManagerError(
                "No DBD input mappings were found in the selected Input.ini."
            )
        axis_source = "file"
        if not axis_mappings:
            axis_source = "game defaults"
            for axis, scale, key in DEFAULT_AXIS_MAPPINGS:
                axis_mappings.setdefault(axis, []).append({"key": key, "scale": scale})
        return input_file, {
            "actions": actions,
            "action_mappings": action_mappings,
            "axis_mappings": axis_mappings,
            "axis_source": axis_source,
        }

    def input_presets(self):
        presets = {}
        preset_dir = self.input_preset_dir()
        if not preset_dir.is_dir():
            return presets
        prefix = f"{self.input_settings_path.name}-"
        for preset_file in preset_dir.glob(f"{self.input_settings_path.name}-*"):
            name = preset_file.name.removeprefix(prefix)
            if not name:
                continue
            try:
                _input_file, data = self.read_input_settings(preset_file)
                presets[name] = data
            except ManagerError:
                continue
        return presets

    def input_preset_dir(self):
        return self.input_settings_path.resolve().parent

    def input_preset_path(self, name):
        name = self.validate_graphics_preset_name(name)
        return self.input_preset_dir() / f"{self.input_settings_path.name}-{name}"

    def save_input_preset(self, name, data):
        name = self.validate_graphics_preset_name(name)
        preset_file = self.input_preset_path(name)
        self.save_input_settings(
            self.input_settings_path,
            data,
            create_backup=False,
            destination=preset_file,
        )
        return name

    def delete_input_preset(self, name):
        name = self.validate_graphics_preset_name(name)
        preset_file = self.input_preset_path(name)
        if not preset_file.is_file():
            raise ManagerError(f"The input preset '{name}' was not found.")
        try:
            preset_file.unlink()
        except OSError as exc:
            raise ManagerError(f"The input preset could not be deleted: {exc}") from exc

    def _input_mapping_lines(self, data):
        lines = []
        action_mappings = data.get("action_mappings")
        if not isinstance(action_mappings, dict):
            action_mappings = {
                action: [{"key": key} for key in keys]
                for action, keys in data.get("actions", {}).items()
            }
        for action, mappings in action_mappings.items():
            seen = set()
            for mapping in mappings:
                if isinstance(mapping, str):
                    mapping = {"key": mapping}
                key = str(mapping.get("key", "")).strip()
                signature = (
                    key,
                    bool(mapping.get("shift")),
                    bool(mapping.get("ctrl")),
                    bool(mapping.get("alt")),
                    bool(mapping.get("cmd")),
                )
                if key and signature not in seen:
                    lines.append(self._format_action_mapping(action, mapping))
                    seen.add(signature)

        axis_mappings = data.get("axis_mappings", {})
        if isinstance(axis_mappings, dict):
            for axis, mappings in axis_mappings.items():
                seen = set()
                for mapping in mappings:
                    key = str(mapping.get("key", "")).strip()
                    try:
                        scale = float(mapping.get("scale", 1.0))
                    except (TypeError, ValueError):
                        continue
                    signature = (key, scale)
                    if key and signature not in seen:
                        lines.append(
                            self._format_axis_mapping(
                                axis,
                                {"key": key, "scale": scale},
                            )
                        )
                        seen.add(signature)
        return lines

    @staticmethod
    def _merge_input_mapping_metadata(data, current):
        merged = dict(data)
        if not isinstance(merged.get("action_mappings"), dict):
            current_mappings = current.get("action_mappings", {})
            action_mappings = {}
            for action, keys in merged.get("actions", {}).items():
                existing = {
                    mapping.get("key"): mapping
                    for mapping in current_mappings.get(action, [])
                    if isinstance(mapping, dict) and mapping.get("key")
                }
                action_mappings[action] = [
                    dict(existing.get(str(key).strip(), {"key": str(key).strip()}))
                    for key in keys
                    if str(key).strip()
                ]
            merged["action_mappings"] = action_mappings
        if not isinstance(merged.get("axis_mappings"), dict):
            merged["axis_mappings"] = current.get("axis_mappings", {})
        return merged

    def _replace_input_mapping_lines(self, text, data):
        new_mapping_lines = self._input_mapping_lines(data)
        lines = text.splitlines(keepends=True)
        output = []
        section = None
        inserted = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if section == INPUT_SETTINGS_SECTION and not inserted:
                    output.extend(f"{mapping}\n" for mapping in new_mapping_lines)
                    inserted = True
                section = stripped[1:-1]
                output.append(line)
                continue
            if section == INPUT_SETTINGS_SECTION and stripped.startswith(
                ("ActionMappings=(", "AxisMappings=(")
            ):
                continue
            output.append(line)

        if section == INPUT_SETTINGS_SECTION and not inserted:
            output.extend(f"{mapping}\n" for mapping in new_mapping_lines)
            inserted = True
        if not inserted:
            if output and output[-1].strip():
                output.append("\n")
            output.append(f"[{INPUT_SETTINGS_SECTION}]\n")
            output.extend(f"{mapping}\n" for mapping in new_mapping_lines)
        return "".join(output)

    def save_input_settings(self, path, data, create_backup=True, destination=None):
        input_file, current = self.read_input_settings(path)
        try:
            original_text = input_file.read_text(encoding="utf-8-sig")
            merged_data = self._merge_input_mapping_metadata(data, current)
            updated_text = self._replace_input_mapping_lines(
                original_text,
                merged_data,
            )
            backup = None
            target_file = Path(destination).resolve() if destination else input_file
            if create_backup and target_file == input_file:
                backup = self._create_backup(input_file)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target_file, updated_text)
        except OSError as exc:
            raise ManagerError(f"The input settings could not be saved: {exc}") from exc
        return backup

    def graphics_preset_path(self, name):
        name = self.validate_graphics_preset_name(name)
        return self.graphics_preset_dir() / f"{self.game_settings_path.name}-{name}"

    def graphics_preset_dir(self):
        return self.game_settings_path.resolve().parent

    def _migrate_graphics_presets_to_files(self):
        if not self.game_settings_path.is_file():
            return

        legacy_presets = self.config.get("graphics_presets", {})
        migrated = False
        if isinstance(legacy_presets, dict):
            for name, settings in legacy_presets.items():
                try:
                    preset_file = self.graphics_preset_path(name)
                    if preset_file.exists():
                        continue
                    self.save_game_settings(
                        self.game_settings_path,
                        settings,
                        create_backup=False,
                        destination=preset_file,
                    )
                    migrated = True
                except ManagerError:
                    continue

        legacy_dir = self.paths.legacy_graphics_preset_dir
        if legacy_dir.is_dir():
            for old_file in legacy_dir.glob("*.ini"):
                name = old_file.stem
                if name.startswith("GameUserSettings - "):
                    name = name.removeprefix("GameUserSettings - ")
                try:
                    new_file = self.graphics_preset_path(name)
                    if not new_file.exists():
                        shutil.copy2(old_file, new_file)
                    migrated = True
                except (OSError, ManagerError):
                    continue

        if migrated:
            self.config["graphics_presets"] = {}
            self._write_config()

    @staticmethod
    def _graphics_settings_from_values(values):
        def get(section, key, default):
            return values.get((section, key), default)

        def get_int(section, key, default):
            try:
                return int(float(get(section, key, default)))
            except (TypeError, ValueError) as exc:
                raise ManagerError(
                    "A graphics preset contains invalid values."
                ) from exc

        def get_bool(section, key, default=False):
            return str(get(section, key, str(default))).casefold() == "true"

        return EGSManager._normalize_graphics_settings(
            {
                "width": get_int(GAME_SETTINGS_SECTION, "ResolutionSizeX", 1920),
                "height": get_int(GAME_SETTINGS_SECTION, "ResolutionSizeY", 1080),
                "fps": get_int(GAME_SETTINGS_SECTION, "FrameRateLimit", 0),
                "render_scale": get_int(
                    GAME_SETTINGS_SECTION,
                    "ScreenRenderSize",
                    get(SCALABILITY_SECTION, "sg.ResolutionQuality", 100),
                ),
                "fullscreen_mode": get_int(
                    GAME_SETTINGS_SECTION,
                    "FullscreenMode",
                    1,
                ),
                "vsync": get_bool(GAME_SETTINGS_SECTION, "bUseVSync"),
                "dynamic_resolution": get_bool(
                    GAME_SETTINGS_SECTION,
                    "bUseDynamicResolution",
                ),
                "main_volume": get_int(
                    GAME_SETTINGS_SECTION,
                    "MainVolume",
                    100,
                ),
                "main_volume_on": get_bool(
                    GAME_SETTINGS_SECTION,
                    "MainVolumeOn",
                    True,
                ),
                "menu_music_volume": get_int(
                    GAME_SETTINGS_SECTION,
                    "MenuMusicVolume",
                    100,
                ),
                "menu_music_volume_on": get_bool(
                    GAME_SETTINGS_SECTION,
                    "MenuMusicVolumeOn",
                    True,
                ),
                "quality": {
                    key: get_int(SCALABILITY_SECTION, key, 0) for key in QUALITY_KEYS
                },
            }
        )

    def read_game_settings(self, path=None):
        settings_file = Path(path or self.game_settings_path).resolve()
        if not settings_file.is_file():
            raise ManagerError(
                f"GameUserSettings.ini was not found at '{settings_file}'."
            )
        try:
            text = settings_file.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ManagerError(f"The game settings could not be read: {exc}") from exc
        return settings_file, self._parse_ini_values(text)

    @staticmethod
    def _update_ini_text(text, updates):
        return update_values(text, updates)

    @staticmethod
    def _normalize_graphics_settings(settings):
        try:
            width = int(settings["width"])
            height = int(settings["height"])
            fps = int(settings["fps"])
            render_scale = int(settings["render_scale"])
            fullscreen_mode = int(settings["fullscreen_mode"])
            main_volume = int(settings.get("main_volume", 100))
            menu_music_volume = int(settings.get("menu_music_volume", 100))
            quality = {key: int(value) for key, value in settings["quality"].items()}
        except (KeyError, TypeError, ValueError) as exc:
            raise ManagerError("One or more graphics settings are invalid.") from exc

        if not 640 <= width <= 16384 or not 360 <= height <= 8640:
            raise ManagerError("Resolution is outside the supported editor range.")
        if not 0 <= fps <= 120:
            raise ManagerError("FPS limit must be between 0 and 120.")
        if not 10 <= render_scale <= 100:
            raise ManagerError("Render scale must be between 10 and 100 percent.")
        if fullscreen_mode not in {0, 1, 2}:
            raise ManagerError("The selected display mode is invalid.")
        if not 0 <= main_volume <= 100:
            raise ManagerError("Main volume must be between 0 and 100 percent.")
        if not 0 <= menu_music_volume <= 100:
            raise ManagerError("Menu music volume must be between 0 and 100 percent.")
        if any(value not in {0, 1, 2, 3} for value in quality.values()):
            raise ManagerError("Quality values must be between Low and Ultra.")

        return {
            "width": width,
            "height": height,
            "fps": fps,
            "render_scale": render_scale,
            "fullscreen_mode": fullscreen_mode,
            "vsync": bool(settings["vsync"]),
            "dynamic_resolution": bool(settings["dynamic_resolution"]),
            "main_volume": main_volume,
            "main_volume_on": bool(settings.get("main_volume_on", True)),
            "menu_music_volume": menu_music_volume,
            "menu_music_volume_on": bool(settings.get("menu_music_volume_on", True)),
            "quality": quality,
        }

    def save_game_settings(self, path, settings, create_backup=True, destination=None):
        settings_file, current = self.read_game_settings(path)
        settings = dict(settings)
        settings.setdefault(
            "main_volume",
            current.get((GAME_SETTINGS_SECTION, "MainVolume"), 100),
        )
        settings.setdefault(
            "main_volume_on",
            str(current.get((GAME_SETTINGS_SECTION, "MainVolumeOn"), "True")).casefold()
            == "true",
        )
        settings.setdefault(
            "menu_music_volume",
            current.get((GAME_SETTINGS_SECTION, "MenuMusicVolume"), 100),
        )
        settings.setdefault(
            "menu_music_volume_on",
            str(
                current.get(
                    (GAME_SETTINGS_SECTION, "MenuMusicVolumeOn"),
                    "True",
                )
            ).casefold()
            == "true",
        )
        normalized = self._normalize_graphics_settings(settings)
        width = normalized["width"]
        height = normalized["height"]
        fps = normalized["fps"]
        render_scale = normalized["render_scale"]
        fullscreen_mode = normalized["fullscreen_mode"]
        quality = normalized["quality"]
        updates = {
            (GAME_SETTINGS_SECTION, "ResolutionSizeX"): str(width),
            (GAME_SETTINGS_SECTION, "ResolutionSizeY"): str(height),
            (GAME_SETTINGS_SECTION, "LastUserConfirmedResolutionSizeX"): str(width),
            (GAME_SETTINGS_SECTION, "LastUserConfirmedResolutionSizeY"): str(height),
            (GAME_SETTINGS_SECTION, "FullscreenMode"): str(fullscreen_mode),
            (GAME_SETTINGS_SECTION, "LastConfirmedFullscreenMode"): str(
                fullscreen_mode
            ),
            (GAME_SETTINGS_SECTION, "PreferredFullscreenMode"): str(fullscreen_mode),
            (GAME_SETTINGS_SECTION, "FrameRateLimit"): f"{float(fps):.6f}",
            (GAME_SETTINGS_SECTION, "FPSLimitMode"): str(fps),
            (GAME_SETTINGS_SECTION, "bUseVSync"): str(normalized["vsync"]),
            (GAME_SETTINGS_SECTION, "bUseDynamicResolution"): str(
                normalized["dynamic_resolution"]
            ),
            (GAME_SETTINGS_SECTION, "MainVolume"): str(normalized["main_volume"]),
            (GAME_SETTINGS_SECTION, "MainVolumeOn"): str(normalized["main_volume_on"]),
            (GAME_SETTINGS_SECTION, "MenuMusicVolume"): str(
                normalized["menu_music_volume"]
            ),
            (GAME_SETTINGS_SECTION, "MenuMusicVolumeOn"): str(
                normalized["menu_music_volume_on"]
            ),
            (GAME_SETTINGS_SECTION, "ScreenRenderSize"): str(render_scale),
            (GAME_SETTINGS_SECTION, "AutoAdjust"): "False",
            (GAME_SETTINGS_SECTION, "AutoScalabilitySet"): "False",
            (SCALABILITY_SECTION, "sg.ResolutionQuality"): str(render_scale),
        }
        for key, value in quality.items():
            updates[(SCALABILITY_SECTION, key)] = str(value)
        quality_values = set(quality.values())
        if len(quality_values) == 1:
            updates[(GAME_SETTINGS_SECTION, "ScalabilityLevel")] = str(
                next(iter(quality_values))
            )

        try:
            original_text = settings_file.read_text(encoding="utf-8-sig")
            updated_text = self._update_ini_text(original_text, updates)
            backup = None
            target_file = Path(destination).resolve() if destination else settings_file
            if create_backup and target_file == settings_file:
                backup = self._create_backup(settings_file)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target_file, updated_text)
        except OSError as exc:
            raise ManagerError(f"The game settings could not be saved: {exc}") from exc
        return backup

    @staticmethod
    def unlock_file(path):
        path = Path(path)
        if path.exists():
            mode = path.stat().st_mode
            if not bool(mode & stat.S_IWRITE):
                path.chmod(mode | stat.S_IWRITE)

    @staticmethod
    def lock_file(path):
        path = Path(path)
        mode = path.stat().st_mode
        path.chmod(mode & ~stat.S_IWRITE)

    @staticmethod
    def _create_backup(path):
        path = Path(path)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = path.with_name(f"{path.name}.backup-{timestamp}")
        shutil.copy2(path, backup)
        return backup

    def _apply_preset_file(
        self,
        preset_file,
        target_file,
        *,
        description,
        create_backup,
        lock,
    ):
        try:
            self.unlock_file(target_file)
            backup = self._create_backup(target_file) if create_backup else None
            shutil.copy2(preset_file, target_file)
            if lock:
                self.lock_file(target_file)
        except OSError as exc:
            raise ManagerError(
                f"The {description} could not be applied: {exc}"
            ) from exc
        return backup

    def apply_graphics_preset_file(self, name, create_backup=False, lock=True):
        name = self.validate_graphics_preset_name(name)
        preset_file = self.graphics_preset_path(name)
        if not preset_file.is_file():
            raise ManagerError(f"The graphics preset '{name}' was not found.")
        settings_file = self.game_settings_path.resolve()
        if not settings_file.is_file():
            raise ManagerError(
                f"GameUserSettings.ini was not found at '{settings_file}'."
            )
        return self._apply_preset_file(
            preset_file,
            settings_file,
            description="graphics preset",
            create_backup=create_backup,
            lock=lock,
        )

    def apply_input_preset_file(self, name, create_backup=False, lock=True):
        name = self.validate_graphics_preset_name(name)
        preset_file = self.input_preset_path(name)
        if not preset_file.is_file():
            raise ManagerError(f"The input preset '{name}' was not found.")
        input_file = self.input_settings_path.resolve()
        if not input_file.is_file():
            raise ManagerError(f"Input.ini was not found at '{input_file}'.")
        return self._apply_preset_file(
            preset_file,
            input_file,
            description="input preset",
            create_backup=create_backup,
            lock=lock,
        )

    def create_account(self, name):
        name = self.validate_account_name(name)
        path = self.account_path(name)
        if path.exists():
            raise ManagerError(f"The profile '{name}' already exists.")
        path.mkdir(parents=True)
        if self.dbd_path and self.dbd_path.exists() and self.has_dbd_template():
            self.sync_dbd_installation(accounts=[name])
        return name

    def remove_account(self, name):
        path = self.account_path(name)
        if not path.exists():
            raise ManagerError(f"The profile '{name}' was not found.")
        shutil.rmtree(path)
        if self.active == name:
            self.config["active"] = None
            self._write_config()

    def export_account(self, name, destination):
        source = self.account_path(name)
        if not source.is_dir():
            raise ManagerError(f"The profile '{name}' was not found.")

        destination = Path(destination).expanduser().resolve()
        if destination.is_relative_to(source):
            raise ManagerError(
                "Choose an export destination outside the profile folder."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        excluded_names = {"installed.json"}
        excluded_folders = {"tmp", "metadata", "manifests", "__pycache__"}

        try:
            with zipfile.ZipFile(
                destination,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                metadata = {
                    "format": "dbd-account-export",
                    "version": 1,
                    "profile_name": name,
                    "exported_at": datetime.now(UTC).isoformat(),
                    "contains_authentication_data": True,
                }
                archive.writestr(
                    f"{name}/export_info.json",
                    json.dumps(metadata, indent=2),
                )
                for item in source.rglob("*"):
                    relative = item.relative_to(source)
                    if any(part in excluded_folders for part in relative.parts):
                        continue
                    if item.is_file() and item.name not in excluded_names:
                        archive.write(item, Path(name) / relative)
        except OSError as exc:
            raise ManagerError(f"The profile could not be exported: {exc}") from exc
        return destination

    def set_active(self, name):
        name = self.validate_account_name(name)
        if not self.account_path(name).exists():
            raise ManagerError(f"The profile '{name}' was not found.")
        self.config["active"] = name
        self._write_config()

    def installed_file(self, account):
        return self.account_path(account) / "legendary" / "installed.json"

    def game_metadata_file(self, account, app_name=DBD_APP_NAME):
        """Return Legendary's cached catalog metadata path for a profile."""

        return (
            self.account_path(account) / "legendary" / "metadata" / f"{app_name}.json"
        )

    def has_game_metadata(self, account, app_name=DBD_APP_NAME):
        """Check that cached metadata contains the fields Legendary needs to launch."""

        metadata_file = self.game_metadata_file(account, app_name)
        try:
            data = json.loads(metadata_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        asset_infos = data.get("asset_infos") if isinstance(data, dict) else None
        return (
            isinstance(data, dict)
            and data.get("app_name") == app_name
            and isinstance(data.get("metadata"), dict)
            and isinstance(asset_infos, dict)
            and isinstance(asset_infos.get("Windows"), dict)
        )

    def _eac_splash_backup_path(self, splash_file):
        identity = hashlib.sha256(
            str(splash_file.resolve()).casefold().encode("utf-8")
        ).hexdigest()[:12]
        return self.paths.data_dir / f"eac_splash_original-{identity}.png"

    @staticmethod
    def _splash_font(size, bold=False):
        windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        candidates = (
            windows_dir / "Fonts" / ("segoeuib.ttf" if bold else "segoeui.ttf"),
            windows_dir / "Fonts" / ("arialbd.ttf" if bold else "arial.ttf"),
        )
        for candidate in candidates:
            if candidate.is_file():
                try:
                    return ImageFont.truetype(str(candidate), size=size)
                except OSError:
                    continue
        return ImageFont.load_default()

    def _render_profile_splash(self, source_file, profile, destination):
        with Image.open(source_file) as source:
            image = source.convert("RGBA")

        width, height = image.size
        if width < 320 or height < 180:
            raise ManagerError(
                "The EAC splash image is too small to add a readable profile name."
            )

        margin = max(18, round(min(width, height) * 0.045))
        horizontal_padding = max(28, round(width * 0.045))
        vertical_padding = max(18, round(height * 0.04))
        name_size = max(24, round(height * 0.08))
        name_font = self._splash_font(name_size, bold=True)
        draw = ImageDraw.Draw(image, "RGBA")
        available_width = width - (margin + horizontal_padding) * 2

        while name_size > 18:
            name_box = draw.textbbox((0, 0), profile, font=name_font)
            if name_box[2] - name_box[0] <= available_width:
                break
            name_size -= 2
            name_font = self._splash_font(name_size, bold=True)

        name_box = draw.textbbox((0, 0), profile, font=name_font)
        name_width = name_box[2] - name_box[0]
        name_height = name_box[3] - name_box[1]
        panel_width = min(width - margin * 2, name_width + horizontal_padding * 2)
        panel_height = name_height + vertical_padding * 2
        panel_left = round((width - panel_width) / 2)
        panel_top = round((height - panel_height) / 2)
        panel_box = (
            panel_left,
            panel_top,
            panel_left + panel_width,
            panel_top + panel_height,
        )
        draw.rectangle(panel_box, fill=(0, 0, 0, 255))
        text_x = round(width / 2 - (name_box[0] + name_box[2]) / 2)
        text_y = round(height / 2 - (name_box[1] + name_box[3]) / 2)
        draw.text(
            (text_x, text_y),
            profile,
            font=name_font,
            fill=(255, 255, 255, 255),
        )

        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("BetterTogetherSplash", "1")
        metadata.add_text("BetterTogetherProfile", profile)
        metadata.add_text("BetterTogetherBase", str(source_file))
        image.convert("RGB").save(
            destination,
            format="PNG",
            pnginfo=metadata,
            optimize=True,
        )

    def prepare_eac_splash(self, profile, game_path=None):
        profile = self.validate_account_name(profile)
        if Image is None:
            raise ManagerError(
                "Profile-labelled EAC splash images require Pillow. "
                "Use the packaged launcher or install its requirements."
            )
        selected_game_path = game_path or self.dbd_path
        if not selected_game_path:
            raise ManagerError("Select the Dead by Daylight installation folder first.")
        game_path = self.validate_dbd_path(selected_game_path)
        splash_file = game_path / EAC_SPLASH_RELATIVE
        if not splash_file.is_file():
            raise ManagerError(
                f"The EAC splash image was not found at '{splash_file}'."
            )

        backup_file = self._eac_splash_backup_path(splash_file)
        temporary_file = splash_file.with_name(
            f".{splash_file.name}.better-together-{os.getpid()}.tmp"
        )
        try:
            with Image.open(splash_file) as current:
                generated_by_launcher = current.info.get("BetterTogetherSplash") == "1"
                current.verify()

            if generated_by_launcher and not backup_file.is_file():
                raise ManagerError(
                    "The original EAC splash backup is missing. Restore "
                    f"'{splash_file}' through Epic Games or replace it with an "
                    "unmodified splash image, then launch again."
                )

            if not generated_by_launcher:
                shutil.copy2(splash_file, backup_file)

            self._render_profile_splash(
                backup_file,
                profile,
                temporary_file,
            )
            original_mode = splash_file.stat().st_mode
            was_readonly = not bool(original_mode & stat.S_IWRITE)
            if was_readonly:
                splash_file.chmod(original_mode | stat.S_IWRITE)
            os.replace(temporary_file, splash_file)
            if was_readonly:
                splash_file.chmod(original_mode)
        except (OSError, ValueError) as exc:
            raise ManagerError(
                "The profile-labelled EAC splash could not be created. "
                f"Close any running DBD/EAC clients and check access to "
                f"'{splash_file}': {exc}"
            ) from exc
        finally:
            if temporary_file.exists():
                try:
                    temporary_file.unlink()
                except OSError:
                    pass
        return splash_file, backup_file

    def validate_dbd_path(self, path):
        game_path = Path(path).expanduser().resolve()
        if not game_path.is_dir():
            raise ManagerError("The selected Dead by Daylight folder does not exist.")
        if not (game_path / DBD_EXECUTABLE).is_file():
            raise ManagerError(
                f"'{DBD_EXECUTABLE}' was not found in the selected folder. "
                "Please select the Dead by Daylight installation root."
            )
        return game_path

    def set_dbd_path(self, path):
        game_path = self.validate_dbd_path(path)
        self.config["dbd_path"] = str(game_path)
        self._write_config()
        return game_path

    def _read_installed_games(self, account):
        installed_file = self.installed_file(account)
        if not installed_file.exists():
            return {}
        try:
            data = json.loads(installed_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManagerError(
                f"Could not read installed games for profile '{account}': {exc}"
            ) from exc
        return data if isinstance(data, dict) else {}

    def _migrate_existing_dbd_path(self):
        for account in self.accounts():
            game = self._read_installed_games(account).get(DBD_APP_NAME)
            if not isinstance(game, dict):
                continue
            install_path = game.get("install_path")
            if install_path and (Path(install_path) / DBD_EXECUTABLE).is_file():
                self.config["dbd_path"] = str(Path(install_path).resolve())
                self._write_config()
                return

    def _find_dbd_template(self):
        template_file = self.paths.dbd_template_file
        if template_file.exists():
            try:
                template = json.loads(template_file.read_text(encoding="utf-8"))
                if (
                    isinstance(template, dict)
                    and template.get("app_name") == DBD_APP_NAME
                ):
                    return template
            except (OSError, json.JSONDecodeError):
                pass

        candidates = []
        for account in self.accounts():
            game = self._read_installed_games(account).get(DBD_APP_NAME)
            if isinstance(game, dict):
                candidates.append(game)
        if not candidates:
            return None
        return max(candidates, key=lambda game: len(game.get("base_urls", [])))

    def has_dbd_template(self):
        return self._find_dbd_template() is not None

    def sync_dbd_installation(self, accounts=None):
        if not self.dbd_path:
            raise ManagerError("Please select the Dead by Daylight folder first.")
        game_path = self.validate_dbd_path(self.dbd_path)
        template = self._find_dbd_template()
        if not template:
            raise ManagerError(
                "Dead by Daylight metadata is not available yet. "
                "Log in to one profile and select the game folder again."
            )

        template = dict(template)
        template["app_name"] = DBD_APP_NAME
        template["title"] = "Dead by Daylight"
        template["executable"] = DBD_EXECUTABLE
        template["install_path"] = str(game_path)
        atomic_write_json(self.paths.dbd_template_file, template)

        target_accounts = self.accounts() if accounts is None else accounts
        synced = 0
        for account in target_accounts:
            games = self._read_installed_games(account)
            games[DBD_APP_NAME] = dict(template)
            installed_file = self.installed_file(account)
            installed_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(installed_file, games)
            synced += 1
        return synced

    def legendary_executable(self):
        if getattr(sys, "frozen", False):
            bundled_exe = Path(sys._MEIPASS) / "legendary.exe"
            if bundled_exe.exists():
                return str(bundled_exe)

        source_root = Path(__file__).resolve().parents[1]
        project_candidates = (
            source_root / "vendor" / "legendary.exe",
            source_root / "better_together" / "vendor" / "legendary.exe",
        )
        for project_exe in project_candidates:
            if project_exe.is_file():
                return str(project_exe)

        local_exe = self.paths.legendary_executable
        if local_exe.is_file():
            return str(local_exe)
        executable = shutil.which("legendary")
        if executable:
            return executable
        raise ManagerError(
            "Legendary was not found. Expected the bundled version, "
            f"'{project_candidates[0]}', '{local_exe}', or an entry in PATH."
        )

    def legendary_auth_executable(self):
        if getattr(sys, "frozen", False):
            bundled_exe = Path(sys._MEIPASS) / "legendary-auth.exe"
            if bundled_exe.is_file():
                return str(bundled_exe)

        source_root = Path(__file__).resolve().parents[1]
        candidates = (
            source_root / "vendor" / "legendary-auth.exe",
            self.paths.data_dir / "legendary-auth.exe",
        )
        for executable in candidates:
            if executable.is_file():
                return str(executable)
        raise ManagerError(
            "The Epic Games sign-in component was not found. Run build.ps1 "
            "to download and package it."
        )

    def legendary_env(self, account):
        if not self.account_path(account).exists():
            raise ManagerError(f"The profile '{account}' was not found.")
        config_dir = self.account_path(account)
        config_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = str(config_dir)
        return env

    def command(self, arguments, account=None):
        account = account or self.active
        if not account:
            raise ManagerError("Please select an active profile first.")
        return [self.legendary_executable(), *arguments], self.legendary_env(account)

    def auth_command(self, arguments, account=None):
        account = account or self.active
        if not account:
            raise ManagerError("Please select an active profile first.")
        return [self.legendary_auth_executable(), *arguments], self.legendary_env(
            account
        )
