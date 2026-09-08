"""Subprocess and launch-preset orchestration, independent of Tkinter."""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .constants import (
    DBD_APP_NAME,
    GRAPHICS_PRESET_SETTLE_SECONDS,
    INPUT_PRESET_SETTLE_SECONDS,
    WINDOWS_NO_CONSOLE,
)
from .errors import ManagerError, OperationCancelled


@dataclass(frozen=True, slots=True)
class ProcessResult:
    return_code: int


class CommandRunner:
    """Single boundary around platform-specific process creation."""

    def __init__(self) -> None:
        self._streaming_processes: set[subprocess.Popen[str]] = set()
        self._lock = threading.Lock()

    def launch_detached(self, command: Sequence[str], env: Mapping[str, str]) -> None:
        subprocess.Popen(
            list(command),
            env=dict(env),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=WINDOWS_NO_CONSOLE,
        )

    def stream(
        self,
        command: Sequence[str],
        env: Mapping[str, str],
        on_line: Callable[[str], None],
    ) -> ProcessResult:
        process = subprocess.Popen(
            list(command),
            env=dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=WINDOWS_NO_CONSOLE,
        )
        with self._lock:
            self._streaming_processes.add(process)
        try:
            assert process.stdout is not None
            for line in process.stdout:
                on_line(line)
            return ProcessResult(process.wait())
        finally:
            with self._lock:
                self._streaming_processes.discard(process)

    def terminate_streaming(self) -> None:
        """Request termination of commands owned by the launcher UI."""

        with self._lock:
            processes = tuple(self._streaming_processes)
        for process in processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass


class PresetLauncher:
    """Runs a launch preset and reports progress through UI-neutral events."""

    def __init__(
        self,
        manager: Any,
        runner: CommandRunner,
        emit: Callable[[str, str], None],
        *,
        sleeper: Callable[[float], None] = time.sleep,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> None:
        self.manager = manager
        self.runner = runner
        self.emit = emit
        self.sleeper = sleeper
        self.cancelled = cancelled

    def run(
        self,
        entries: Iterable[Mapping[str, Any]],
        delay_seconds: int,
        skip_version_check: bool,
        launch_arguments: Sequence[str] = (),
    ) -> None:
        normalized_entries = list(entries)
        settings_locked = False
        input_locked = False
        try:
            accounts = list(
                dict.fromkeys(str(entry["account"]) for entry in normalized_entries)
            )
            for account in accounts:
                self._ensure_game_metadata(account)

            graphics_backup_created = False
            input_backup_created = False
            for index, entry in enumerate(normalized_entries):
                self._raise_if_cancelled()
                account = str(entry["account"])
                graphics_name = entry.get("graphics_preset")
                if graphics_name:
                    backup = self.manager.apply_graphics_preset_file(
                        graphics_name,
                        create_backup=not graphics_backup_created,
                        lock=True,
                    )
                    settings_locked = True
                    graphics_backup_created = True
                    message = (
                        f"Copied and locked graphics preset '{graphics_name}' "
                        f"for '{account}'."
                    )
                    if backup:
                        message += f" Backup: {backup}"
                    self.emit("text", message + "\n")

                input_name = entry.get("input_preset")
                if input_name:
                    backup = self.manager.apply_input_preset_file(
                        input_name,
                        create_backup=not input_backup_created,
                        lock=True,
                    )
                    input_locked = True
                    input_backup_created = True
                    message = (
                        f"Copied and locked input preset '{input_name}' "
                        f"for '{account}'."
                    )
                    if backup:
                        message += f" Backup: {backup}"
                    self.emit("text", message + "\n")

                arguments = ["launch", DBD_APP_NAME]
                if skip_version_check:
                    arguments.append("--skip-version-check")
                arguments.extend(launch_arguments)
                splash_file, backup_file = self.manager.prepare_eac_splash(account)
                self.emit(
                    "text",
                    f"EAC splash labelled for '{account}': {splash_file}\n"
                    f"Original EAC splash backup: {backup_file}\n",
                )
                command, env = self.manager.command(arguments, account=account)
                self.runner.launch_detached(command, env)
                self.emit("text", f"Launched '{account}'.\n")

                if index < len(normalized_entries) - 1:
                    next_account = str(normalized_entries[index + 1]["account"])
                    settle_times = [delay_seconds]
                    if graphics_name:
                        settle_times.append(GRAPHICS_PRESET_SETTLE_SECONDS)
                    if input_name:
                        settle_times.append(INPUT_PRESET_SETTLE_SECONDS)
                    handoff_seconds = max(settle_times)
                    for remaining in range(handoff_seconds, 0, -1):
                        self._raise_if_cancelled()
                        self.emit("status", f"Next: {next_account} in {remaining}s")
                        self.sleeper(1)
        finally:
            if settings_locked:
                try:
                    self.manager.unlock_file(self.manager.game_settings_path)
                except OSError:
                    pass
            if input_locked:
                try:
                    self.manager.unlock_file(self.manager.input_settings_path)
                except OSError:
                    pass

    def _raise_if_cancelled(self) -> None:
        if self.cancelled():
            raise OperationCancelled("The launch preset was cancelled.")

    def _ensure_game_metadata(self, account: str) -> None:
        """Populate Legendary's catalog cache before launching a new profile."""

        if self.manager.has_game_metadata(account):
            return
        self._raise_if_cancelled()
        self.emit("status", f"Preparing Epic game data for {account}")
        self.emit(
            "text",
            f"Preparing Epic game data for '{account}' (first launch only).\n",
        )
        command, env = self.manager.command(["status", "--json"], account=account)
        result = self.runner.stream(
            command,
            env,
            lambda line: self.emit("text", line),
        )
        if result.return_code != 0:
            raise ManagerError(
                f"Could not refresh Epic game data for '{account}'. "
                "Sign in to that profile and try again."
            )
        if not self.manager.has_game_metadata(account):
            raise ManagerError(
                f"Dead by Daylight was not found in the Epic library for '{account}'."
            )
