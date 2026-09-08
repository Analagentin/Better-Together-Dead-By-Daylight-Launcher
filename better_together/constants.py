import os
from pathlib import Path

from .config import AppPaths

_DEFAULT_PATHS = AppPaths.for_current_user()
APP_DIR = _DEFAULT_PATHS.data_dir
CONFIG_FILE = _DEFAULT_PATHS.config_file
DBD_TEMPLATE_FILE = _DEFAULT_PATHS.dbd_template_file
LEGACY_GRAPHICS_PRESET_DIR = _DEFAULT_PATHS.legacy_graphics_preset_dir
DBD_APP_NAME = "Brill"
DBD_EXECUTABLE = "DeadByDaylight.exe"
EAC_SPLASH_RELATIVE = Path("EasyAntiCheat") / "SplashScreen.png"
APP_NAME = "Better Together: Dead By Daylight Launcher"
APP_VERSION = "1.2beta"
APP_DISPLAY_VERSION = "1.2 beta"
GAME_SETTINGS_SECTION = "/Script/DeadByDaylight.DBDGameUserSettings"
INPUT_SETTINGS_SECTION = "/Script/EnhancedInput.EnhancedPlayerInput"
SCALABILITY_SECTION = "ScalabilityGroups"
QUALITY_KEYS = (
    "sg.ViewDistanceQuality",
    "sg.AntiAliasingQuality",
    "sg.ShadowQuality",
    "sg.GlobalIlluminationQuality",
    "sg.ReflectionQuality",
    "sg.PostProcessQuality",
    "sg.TextureQuality",
    "sg.EffectsQuality",
    "sg.FoliageQuality",
    "sg.ShadingQuality",
    "sg.LandscapeQuality",
    "sg.AnimationQuality",
)
WINDOWS_NO_CONSOLE = 0x08000000 if os.name == "nt" else 0
GRAPHICS_PRESET_SETTLE_SECONDS = 30
INPUT_PRESET_SETTLE_SECONDS = 30

MOUSE_KEYS = (
    "",
    "LeftMouseButton",
    "RightMouseButton",
    "MiddleMouseButton",
    "ThumbMouseButton",
    "ThumbMouseButton2",
    "MouseScrollUp",
    "MouseScrollDown",
)
KEYBOARD_KEYS = (
    "",
    "SpaceBar",
    "LeftShift",
    "RightShift",
    "LeftControl",
    "RightControl",
    "LeftAlt",
    "RightAlt",
    "Tab",
    "CapsLock",
    "Escape",
    "BackSpace",
    "Enter",
    "Insert",
    "Delete",
    "Home",
    "End",
    "PageUp",
    "PageDown",
    "Up",
    "Down",
    "Left",
    "Right",
    "F1",
    "F2",
    "F3",
    "F4",
    "F5",
    "F6",
    "F7",
    "F8",
    "F9",
    "F10",
    "F11",
    "F12",
    "Semicolon",
    "Equals",
    "Comma",
    "Hyphen",
    "Period",
    "Slash",
    "Tilde",
    "LeftBracket",
    "Backslash",
    "RightBracket",
    "Apostrophe",
    "NumLock",
    "ScrollLock",
    "Pause",
    "Add",
    "Subtract",
    "Multiply",
    "Divide",
    "Decimal",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Zero",
    *tuple(chr(code) for code in range(ord("A"), ord("Z") + 1)),
)
GAMEPAD_KEYS = (
    "",
    "Gamepad_FaceButton_Bottom",
    "Gamepad_FaceButton_Right",
    "Gamepad_FaceButton_Left",
    "Gamepad_FaceButton_Top",
    "Gamepad_LeftShoulder",
    "Gamepad_RightShoulder",
    "Gamepad_LeftTrigger",
    "Gamepad_RightTrigger",
    "Gamepad_LeftThumbstick",
    "Gamepad_RightThumbstick",
    "Gamepad_Special_Left",
    "Gamepad_Special_Right",
    "Gamepad_DPad_Up",
    "Gamepad_DPad_Down",
    "Gamepad_DPad_Left",
    "Gamepad_DPad_Right",
    "Gamepad_LeftStick_Up",
    "Gamepad_LeftStick_Down",
    "Gamepad_LeftStick_Left",
    "Gamepad_LeftStick_Right",
    "Gamepad_RightStick_Up",
    "Gamepad_RightStick_Down",
    "Gamepad_RightStick_Left",
    "Gamepad_RightStick_Right",
)
