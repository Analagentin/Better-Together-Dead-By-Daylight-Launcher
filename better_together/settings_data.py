"""Unreal Engine INI helpers and Dead by Daylight input metadata."""

from __future__ import annotations

import re
from collections.abc import Mapping

IniKey = tuple[str, str]


def parse_values(text: str) -> dict[IniKey, str]:
    """Parse scalar values while ignoring comments and preserving section names."""

    values: dict[IniKey, str] = {}
    section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section and "=" in raw_line:
            key, value = raw_line.split("=", 1)
            values[(section, key.strip())] = value.strip()
    return values


def update_values(text: str, updates: Mapping[IniKey, str]) -> str:
    """Update requested keys and leave unrelated lines and sections untouched."""

    lines = text.splitlines(keepends=True)
    section: str | None = None
    applied: set[IniKey] = set()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if section:
                for (target_section, key), value in updates.items():
                    if target_section == section and (section, key) not in applied:
                        output.append(f"{key}={value}\n")
                        applied.add((section, key))
            section = stripped[1:-1]
            output.append(line)
            continue

        if section and "=" in line and not stripped.startswith((";", "#")):
            key = line.split("=", 1)[0].strip()
            update_key = (section, key)
            if update_key in updates:
                newline = "\r\n" if line.endswith("\r\n") else "\n"
                output.append(f"{key}={updates[update_key]}{newline}")
                applied.add(update_key)
                continue
        output.append(line)

    if section:
        for (target_section, key), value in updates.items():
            if target_section == section and (target_section, key) not in applied:
                output.append(f"{key}={value}\n")
                applied.add((target_section, key))

    for target_section in dict.fromkeys(section for section, _key in updates):
        missing = [
            (key, value)
            for (section_name, key), value in updates.items()
            if section_name == target_section and (section_name, key) not in applied
        ]
        if missing:
            if output and output[-1].strip():
                output.append("\n")
            output.append(f"[{target_section}]\n")
            output.extend(f"{key}={value}\n" for key, value in missing)
    return "".join(output)


ACTION_CATEGORIES = (
    ("survivor", "Survivor"),
    ("killer", "Killer"),
    ("shared", "Communication"),
    ("spectator", "Spectator"),
)

HIDDEN_ACTIONS = frozenset(
    {
        "PushToTalk",
        "Gesture03",
        "Gesture04",
        "Spectate_Swap",
        "Mash_Camper",
        "DirectionalPadInputUp_Survivor",
        "DirectionalPadInputDown_Survivor",
        "DirectionalPadInputLeft_Survivor",
        "DirectionalPadInputRight_Survivor",
    }
)


def _action(category, label, description=""):
    return {
        "category": category,
        "label": label,
        "description": description,
    }


# Friendly names are based on DBD's current in-game terminology. Raw action
# names remain visible in the editor because Behaviour can reuse an internal
# action in several contextual prompts.
ACTION_METADATA = {
    # Survivor gameplay
    "Action_Camper": _action(
        "survivor",
        "Activate Ability 1",
        "First perk, character, or contextual Survivor ability.",
    ),
    "AbilityTwo_Camper": _action(
        "survivor",
        "Activate Ability 2",
        "Second perk, character, or contextual Survivor ability.",
    ),
    "Interact_Camper": _action(
        "survivor",
        "Interact",
        "Repair, heal, rescue, vault, hide, pick up, and other interactions.",
    ),
    "SecondaryAction_Camper": _action(
        "survivor",
        "Actions / Skill Check",
        "Skill checks and secondary contextual actions.",
    ),
    "Run_Camper": _action("survivor", "Run"),
    "Crouch": _action("survivor", "Crouch"),
    "ItemUse_Camper": _action("survivor", "Use Item"),
    "ItemDrop_Camper": _action("survivor", "Drop Item"),
    "FastInteract_Camper": _action(
        "survivor",
        "Fast / Rushed Interaction",
        "Internal binding used for contextual rushed interactions.",
    ),
    "Mash_Camper": _action(
        "survivor",
        "Legacy Struggle / Mash",
        "Retained by DBD for older and contextual struggle interactions.",
    ),
    "WiggleLeft_Camper": _action("survivor", "Wiggle Left"),
    "WiggleRight_Camper": _action("survivor", "Wiggle Right"),
    "EventAbility_Survivor": _action("survivor", "Event Ability"),
    "DirectionalPadInputUp_Survivor": _action("survivor", "Contextual D-pad Up"),
    "DirectionalPadInputDown_Survivor": _action("survivor", "Contextual D-pad Down"),
    "DirectionalPadInputLeft_Survivor": _action("survivor", "Contextual D-pad Left"),
    "DirectionalPadInputRight_Survivor": _action("survivor", "Contextual D-pad Right"),
    # Killer gameplay
    "Attack_Slasher": _action("killer", "Attack"),
    "Interact_Slasher": _action(
        "killer",
        "Pick Up Survivor / Interactions",
        "Pick up, hook, vault, break, damage, search, and other interactions.",
    ),
    "ItemUse_Slasher": _action("killer", "Use Power"),
    "ItemDrop_Slasher": _action("killer", "Drop Carried Survivor"),
    "SecondaryAction_Slasher": _action("killer", "Secondary Power"),
    "Action_Slasher": _action(
        "killer",
        "Killer Action",
        "Killer-specific contextual or alternate power action.",
    ),
    "AbilityOne_Killer": _action("killer", "Activate Ability 1"),
    "AbilityTwo_Killer": _action(
        "killer",
        "Activate Ability 2 / Secondary Ability",
    ),
    "EventAbility_Killer": _action("killer", "Event Ability"),
    # Communication and gestures
    "Gesture01": _action("shared", "Point"),
    "Gesture02": _action("shared", "Beckon / Come Here"),
    # Spectator controls introduced and expanded in DBD 9.0/9.1.
    "Spectate_Survivor1": _action("spectator", "View Survivor 1"),
    "Spectate_Survivor2": _action("spectator", "View Survivor 2"),
    "Spectate_Survivor3": _action("spectator", "View Survivor 3"),
    "Spectate_Survivor4": _action("spectator", "View Survivor 4"),
    "Spectate_Survivor5": _action("spectator", "View Survivor 5"),
    "Spectate_Survivor6": _action("spectator", "View Survivor 6"),
    "Spectate_Survivor7": _action("spectator", "View Survivor 7"),
    "Spectate_Survivor8": _action("spectator", "View Survivor 8"),
    "Spectate_Killer1": _action("spectator", "View Killer 1"),
    "Spectate_Killer2": _action("spectator", "View Killer 2"),
    "Spectate_Previous": _action("spectator", "Previous Player"),
    "Spectate_Next": _action("spectator", "Next Player"),
    "Spectate_TopBar": _action("spectator", "Show Spectator Top Bar"),
}


MOVEMENT_BINDINGS = (
    {
        "id": "survivor_forward",
        "role": "Survivor",
        "label": "Move Forward",
        "axis": "MoveForwardSurvivor",
        "scale": 1.0,
        "default": "W",
    },
    {
        "id": "survivor_backward",
        "role": "Survivor",
        "label": "Move Backward",
        "axis": "MoveForwardSurvivor",
        "scale": -1.0,
        "default": "S",
    },
    {
        "id": "survivor_left",
        "role": "Survivor",
        "label": "Move Left",
        "axis": "MoveRightSurvivor",
        "scale": -1.0,
        "default": "A",
    },
    {
        "id": "survivor_right",
        "role": "Survivor",
        "label": "Move Right",
        "axis": "MoveRightSurvivor",
        "scale": 1.0,
        "default": "D",
    },
    {
        "id": "killer_forward",
        "role": "Killer",
        "label": "Move Forward",
        "axis": "MoveForwardKiller",
        "scale": 1.0,
        "default": "W",
    },
    {
        "id": "killer_backward",
        "role": "Killer",
        "label": "Move Backward",
        "axis": "MoveForwardKiller",
        "scale": -1.0,
        "default": "S",
    },
    {
        "id": "killer_left",
        "role": "Killer",
        "label": "Move Left",
        "axis": "MoveRightKiller",
        "scale": -1.0,
        "default": "A",
    },
    {
        "id": "killer_right",
        "role": "Killer",
        "label": "Move Right",
        "axis": "MoveRightKiller",
        "scale": 1.0,
        "default": "D",
    },
)


# DBD omits unchanged axis mappings from some platform-specific Input.ini
# files. These are the current generated defaults needed to make movement
# editable without dropping mouse-look or controller-stick mappings.
DEFAULT_AXIS_MAPPINGS = (
    ("MoveForwardSurvivor", 1.0, "W"),
    ("MoveForwardSurvivor", -1.0, "S"),
    ("MoveRightSurvivor", -1.0, "A"),
    ("MoveRightSurvivor", 1.0, "D"),
    ("TurnConstantSurvivor", 1.0, "Gamepad_RightX"),
    ("TurnConstantSurvivor", -1.0, "Left"),
    ("TurnConstantSurvivor", 1.0, "Right"),
    ("LookUp", -1.0, "MouseY"),
    ("Turn", 1.0, "MouseX"),
    ("MoveUp", 1.0, "Q"),
    ("MoveUp", -1.0, "Z"),
    ("MoveForwardSurvivor", 1.0, "Gamepad_LeftY"),
    ("MoveRightSurvivor", 1.0, "Gamepad_LeftX"),
    ("LookUpConstantSurvivor", 1.0, "Gamepad_RightY"),
    ("LookUpConstantSurvivor", 1.0, "Up"),
    ("LookUpConstantSurvivor", -1.0, "Down"),
    ("MoveForwardKiller", 1.0, "W"),
    ("MoveForwardKiller", -1.0, "S"),
    ("MoveRightKiller", -1.0, "A"),
    ("MoveRightKiller", 1.0, "D"),
    ("TurnConstantKiller", 1.0, "Gamepad_RightX"),
    ("TurnConstantKiller", -1.0, "Q"),
    ("TurnConstantKiller", 1.0, "E"),
    ("MoveForwardKiller", 1.0, "Gamepad_LeftY"),
    ("MoveRightKiller", 1.0, "Gamepad_LeftX"),
    ("LookUpConstantKiller", 1.0, "Gamepad_RightY"),
    ("LookUpConstantKiller", 1.0, "Up"),
    ("LookUpConstantKiller", -1.0, "Down"),
)


GAMEPAD_KEY_LABELS = {
    "": "",
    "Gamepad_FaceButton_Bottom": "A / Cross · Bottom face button",
    "Gamepad_FaceButton_Right": "B / Circle · Right face button",
    "Gamepad_FaceButton_Left": "X / Square · Left face button",
    "Gamepad_FaceButton_Top": "Y / Triangle · Top face button",
    "Gamepad_LeftShoulder": "LB / L1 · Left shoulder",
    "Gamepad_RightShoulder": "RB / R1 · Right shoulder",
    "Gamepad_LeftTrigger": "LT / L2 · Left trigger",
    "Gamepad_RightTrigger": "RT / R2 · Right trigger",
    "Gamepad_LeftThumbstick": "LS / L3 · Left stick click",
    "Gamepad_RightThumbstick": "RS / R3 · Right stick click",
    "Gamepad_Special_Left": "View / Share",
    "Gamepad_Special_Right": "Menu / Options",
    "Gamepad_DPad_Up": "D-pad Up",
    "Gamepad_DPad_Down": "D-pad Down",
    "Gamepad_DPad_Left": "D-pad Left",
    "Gamepad_DPad_Right": "D-pad Right",
    "Gamepad_LeftStick_Up": "Left stick Up",
    "Gamepad_LeftStick_Down": "Left stick Down",
    "Gamepad_LeftStick_Left": "Left stick Left",
    "Gamepad_LeftStick_Right": "Left stick Right",
    "Gamepad_RightStick_Up": "Right stick Up",
    "Gamepad_RightStick_Down": "Right stick Down",
    "Gamepad_RightStick_Left": "Right stick Left",
    "Gamepad_RightStick_Right": "Right stick Right",
}


def action_metadata(action_name):
    metadata = ACTION_METADATA.get(action_name)
    if metadata:
        return metadata
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", action_name.replace("_", " "))
    return _action("advanced", " ".join(words.split()), "Unrecognized DBD action.")
