import json
import tempfile
import unittest
from pathlib import Path

from better_together.config import AppPaths, atomic_write_json
from better_together.constants import DBD_APP_NAME, DBD_EXECUTABLE
from better_together.manager import EGSManager
from better_together.runtime import PresetLauncher


class MultiInstallManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.manager = EGSManager(AppPaths(root / "data", root / "local"))
        self.profile_library = root / "profiles"
        self.manager.set_account_folder(self.profile_library)
        for account in ("alpha", "beta"):
            (self.profile_library / account).mkdir()

        self.main_install = self._make_install(root / "main-install")
        self.alternate_install = self._make_install(root / "alternate-install")
        self.manager.set_dbd_path(self.main_install)
        atomic_write_json(
            self.manager.paths.dbd_template_file,
            {"app_name": DBD_APP_NAME, "base_urls": ["https://example.invalid"]},
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def _make_install(path):
        path.mkdir(parents=True)
        (path / DBD_EXECUTABLE).touch()
        return path.resolve()

    def test_preset_saves_per_entry_install_and_main_folder_fallback(self):
        self.manager.save_preset(
            "mixed installs",
            [
                {"account": "alpha", "game_path": self.alternate_install},
                "beta",
            ],
            0,
        )

        entries = self.manager.presets()["mixed installs"]["entries"]
        self.assertEqual(entries[0]["game_path"], str(self.alternate_install))
        self.assertIsNone(entries[1]["game_path"])

    def test_sync_can_target_an_alternate_install_without_changing_main_folder(self):
        self.manager.sync_dbd_installation(
            accounts=["alpha"],
            game_path=self.alternate_install,
        )

        installed_file = self.manager.installed_file("alpha")
        installed = json.loads(installed_file.read_text(encoding="utf-8"))
        self.assertEqual(
            installed[DBD_APP_NAME]["install_path"],
            str(self.alternate_install),
        )
        self.assertEqual(self.manager.dbd_path, self.main_install)


class _FakeManager:
    game_settings_path = Path("GameUserSettings.ini")
    input_settings_path = Path("Input.ini")

    def has_game_metadata(self, _account):
        return True

    def command(self, arguments, account=None):
        return ["legendary", *arguments, account], {}


class _FakeRunner:
    def __init__(self):
        self.launches = []

    def launch_detached(self, command, env):
        self.launches.append((command, env))


class MultiInstallRuntimeTests(unittest.TestCase):
    def test_launcher_does_not_require_splash_customization(self):
        manager = _FakeManager()
        runner = _FakeRunner()
        launcher = PresetLauncher(manager, runner, lambda *_event: None)

        launcher.run(
            [
                {"account": "alpha", "game_path": "alternate-install"},
                {"account": "beta"},
            ],
            delay_seconds=0,
            skip_version_check=True,
        )

        self.assertEqual(len(runner.launches), 2)


if __name__ == "__main__":
    unittest.main()
