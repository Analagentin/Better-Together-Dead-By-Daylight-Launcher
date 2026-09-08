import copy
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .constants import (
    APP_NAME,
    GAME_SETTINGS_SECTION,
    GAMEPAD_KEYS,
    KEYBOARD_KEYS,
    MOUSE_KEYS,
    QUALITY_KEYS,
    SCALABILITY_SECTION,
)
from .manager import ManagerError
from .settings_data import (
    ACTION_CATEGORIES,
    GAMEPAD_KEY_LABELS,
    HIDDEN_ACTIONS,
    MOVEMENT_BINDINGS,
    action_metadata,
)
from .ui import COLORS, SmoothCard


class SettingsDialogMixin:
    def open_input_settings(self):
        open_input_settings_dialog(self)

    def open_graphics_settings(self):
        settings_path = self.manager.game_settings_path
        try:
            settings_file, values = self.manager.read_game_settings(settings_path)
        except ManagerError as exc:
            selected = filedialog.askopenfilename(
                title="Select GameUserSettings.ini",
                initialdir=str(settings_path.parent),
                filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
            )
            if not selected:
                messagebox.showerror("Could Not Open Graphics Settings", str(exc))
                return
            try:
                settings_file = self.manager.set_game_settings_path(selected)
                settings_file, values = self.manager.read_game_settings(settings_file)
            except ManagerError as selected_exc:
                messagebox.showerror(
                    "Could Not Open Graphics Settings",
                    str(selected_exc),
                )
                return

        def value(section, key, default):
            return values.get((section, key), default)

        def bool_value(section, key, default=False):
            return value(section, key, str(default)).casefold() == "true"

        dialog = tk.Toplevel(self)
        dialog.title(f"Graphics & Audio Settings - {APP_NAME}")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("900x820")
        dialog.minsize(760, 720)
        dialog.configure(background=COLORS["bg"])
        self._apply_icon_to_window(dialog)

        outer = ttk.Frame(dialog, padding=24)
        outer.pack(fill="both", expand=True)
        self._dialog_header(
            outer,
            "Game settings",
            "Graphics & audio",
            "Adjust display, quality, and sound options or save them as a preset. "
            "Close Dead by Daylight before saving so the game does not overwrite "
            "your changes.",
        )
        path_card_shell = SmoothCard(
            outer,
            padding=12,
            radius=16,
            shadow=True,
        )
        path_card_shell.pack(fill="x", pady=(0, 12))
        path_card = path_card_shell.body
        path_frame = ttk.Frame(path_card, style="CardInner.TFrame")
        path_frame.pack(fill="x")
        path_frame.columnconfigure(0, weight=1)
        ttk.Label(
            path_frame,
            text="GAME SETTINGS FILE",
            style="FieldLabel.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        settings_path_var = tk.StringVar(value=str(settings_file))
        ttk.Entry(
            path_frame,
            textvariable=settings_path_var,
            state="readonly",
        ).grid(row=1, column=0, sticky="ew")

        def select_settings_file():
            selected = filedialog.askopenfilename(
                title="Select GameUserSettings.ini",
                initialdir=str(Path(settings_path_var.get()).parent),
                initialfile="GameUserSettings.ini",
                filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
                parent=dialog,
            )
            if not selected:
                return
            try:
                selected_path = self.manager.set_game_settings_path(selected)
            except ManagerError as exc:
                messagebox.showerror(
                    "Could Not Set Settings Path",
                    str(exc),
                    parent=dialog,
                )
                return
            messagebox.showinfo(
                "Settings Path Saved",
                "The selected path has been saved. Graphics Settings will "
                "close so the new file can be loaded cleanly.",
                parent=dialog,
            )
            settings_path_var.set(str(selected_path))
            dialog.destroy()

        ttk.Button(
            path_frame,
            text="Choose file…",
            command=select_settings_file,
            style="Compact.TButton",
        ).grid(row=1, column=1, padx=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        display_shell = SmoothCard(
            notebook,
            padding=18,
            radius=16,
            shadow=False,
        )
        quality_shell = SmoothCard(
            notebook,
            padding=18,
            radius=16,
            shadow=False,
        )
        audio_shell = SmoothCard(
            notebook,
            padding=18,
            radius=16,
            shadow=False,
        )
        display_tab = display_shell.body
        quality_tab = quality_shell.body
        audio_tab = audio_shell.body
        notebook.add(display_shell, text="Display")
        notebook.add(quality_shell, text="Quality")
        notebook.add(audio_shell, text="Audio")

        width_var = tk.StringVar(
            value=value(GAME_SETTINGS_SECTION, "ResolutionSizeX", "1920")
        )
        height_var = tk.StringVar(
            value=value(GAME_SETTINGS_SECTION, "ResolutionSizeY", "1080")
        )
        mode_names = {
            "Fullscreen": 0,
            "Borderless Window": 1,
            "Windowed": 2,
        }
        stored_mode = int(value(GAME_SETTINGS_SECTION, "FullscreenMode", "1"))
        mode_var = tk.StringVar(
            value=next(
                (name for name, mode in mode_names.items() if mode == stored_mode),
                "Borderless Window",
            )
        )
        fps_value = float(value(GAME_SETTINGS_SECTION, "FrameRateLimit", "0"))
        fps_var = tk.StringVar(value=str(int(fps_value)))
        render_scale_var = tk.StringVar(
            value=value(
                GAME_SETTINGS_SECTION,
                "ScreenRenderSize",
                value(SCALABILITY_SECTION, "sg.ResolutionQuality", "100"),
            )
        )
        vsync_var = tk.BooleanVar(value=bool_value(GAME_SETTINGS_SECTION, "bUseVSync"))
        dynamic_resolution_var = tk.BooleanVar(
            value=bool_value(
                GAME_SETTINGS_SECTION,
                "bUseDynamicResolution",
            )
        )
        main_volume_var = tk.StringVar(
            value=str(int(float(value(GAME_SETTINGS_SECTION, "MainVolume", "100"))))
        )
        main_volume_on_var = tk.BooleanVar(
            value=bool_value(GAME_SETTINGS_SECTION, "MainVolumeOn", True)
        )
        menu_music_volume_var = tk.StringVar(
            value=str(
                int(
                    float(
                        value(
                            GAME_SETTINGS_SECTION,
                            "MenuMusicVolume",
                            "100",
                        )
                    )
                )
            )
        )
        menu_music_volume_on_var = tk.BooleanVar(
            value=bool_value(
                GAME_SETTINGS_SECTION,
                "MenuMusicVolumeOn",
                True,
            )
        )

        display_tab.columnconfigure(1, weight=1)
        display_rows = [
            ("Width:", width_var),
            ("Height:", height_var),
            ("Render scale (10-100%):", render_scale_var),
        ]
        for row, (label, variable) in enumerate(display_rows):
            ttk.Label(display_tab, text=label, style="CardText.TLabel").grid(
                row=row, column=0, sticky="w", pady=5
            )
            ttk.Entry(display_tab, textvariable=variable).grid(
                row=row, column=1, sticky="ew", padx=(10, 0), pady=5
            )

        fps_row = len(display_rows)
        ttk.Label(
            display_tab,
            text="FPS limit (maximum 120):",
            style="CardText.TLabel",
        ).grid(row=fps_row, column=0, sticky="w", pady=5)
        ttk.Spinbox(
            display_tab,
            from_=0,
            to=120,
            textvariable=fps_var,
        ).grid(row=fps_row, column=1, sticky="ew", padx=(10, 0), pady=5)

        mode_row = fps_row + 1
        ttk.Label(
            display_tab,
            text="Display mode:",
            style="CardText.TLabel",
        ).grid(row=mode_row, column=0, sticky="w", pady=5)
        ttk.Combobox(
            display_tab,
            textvariable=mode_var,
            values=list(mode_names),
            state="readonly",
        ).grid(row=mode_row, column=1, sticky="ew", padx=(10, 0), pady=5)
        ttk.Checkbutton(
            display_tab,
            text="Enable VSync",
            variable=vsync_var,
            style="Card.TCheckbutton",
        ).grid(row=mode_row + 1, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Checkbutton(
            display_tab,
            text="Enable dynamic resolution",
            variable=dynamic_resolution_var,
            style="Card.TCheckbutton",
        ).grid(row=mode_row + 2, column=0, columnspan=2, sticky="w", pady=5)

        quality_names = {"Low": 0, "Medium": 1, "High": 2, "Ultra": 3}
        quality_labels = {
            "sg.ViewDistanceQuality": "View distance",
            "sg.AntiAliasingQuality": "Anti-aliasing",
            "sg.ShadowQuality": "Shadows",
            "sg.GlobalIlluminationQuality": "Global illumination",
            "sg.ReflectionQuality": "Reflections",
            "sg.PostProcessQuality": "Post processing",
            "sg.TextureQuality": "Textures",
            "sg.EffectsQuality": "Effects",
            "sg.FoliageQuality": "Foliage",
            "sg.ShadingQuality": "Shading",
            "sg.LandscapeQuality": "Landscape",
            "sg.AnimationQuality": "Animation",
        }
        quality_vars = {}
        quality_tab.columnconfigure(1, weight=1)
        for row, key in enumerate(QUALITY_KEYS):
            raw = int(value(SCALABILITY_SECTION, key, "0"))
            quality_var = tk.StringVar(
                value=next(
                    (name for name, level in quality_names.items() if level == raw),
                    "Low",
                )
            )
            quality_vars[key] = quality_var
            ttk.Label(
                quality_tab,
                text=f"{quality_labels[key]}:",
                style="CardText.TLabel",
            ).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Combobox(
                quality_tab,
                textvariable=quality_var,
                values=list(quality_names),
                state="readonly",
                width=18,
            ).grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=3)

        def apply_quality(level_name):
            for quality_var in quality_vars.values():
                quality_var.set(level_name)

        quality_shortcuts = ttk.Frame(
            quality_tab,
            style="CardInner.TFrame",
        )
        quality_shortcuts.grid(
            row=len(QUALITY_KEYS),
            column=0,
            columnspan=2,
            sticky="w",
            pady=(12, 0),
        )
        for level_name in quality_names:
            ttk.Button(
                quality_shortcuts,
                text=f"All {level_name}",
                command=lambda name=level_name: apply_quality(name),
                style="Compact.TButton",
            ).pack(side="left", padx=(0, 5))

        audio_tab.columnconfigure(0, weight=1)

        def add_volume_control(
            row,
            title,
            description,
            volume_var,
            enabled_var,
        ):
            card = ttk.Frame(audio_tab, style="CardInner.TFrame", padding=14)
            card.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            card.columnconfigure(0, weight=1)
            ttk.Label(
                card,
                text=title,
                style="CardTitle.TLabel",
            ).grid(row=0, column=0, sticky="w")
            ttk.Label(
                card,
                text=description,
                style="CardMuted.TLabel",
                wraplength=650,
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 12))
            ttk.Scale(
                card,
                from_=0,
                to=100,
                variable=volume_var,
                command=lambda current: volume_var.set(str(round(float(current)))),
            ).grid(row=2, column=0, sticky="ew", padx=(0, 12))
            ttk.Spinbox(
                card,
                from_=0,
                to=100,
                increment=1,
                textvariable=volume_var,
                width=7,
                format="%.0f",
            ).grid(row=2, column=1, sticky="e")
            ttk.Checkbutton(
                card,
                text="Enabled",
                variable=enabled_var,
                style="Card.TCheckbutton",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))

        add_volume_control(
            0,
            "Main audio volume",
            "Controls the overall game sound level, including effects and voices.",
            main_volume_var,
            main_volume_on_var,
        )
        add_volume_control(
            1,
            "Menu music volume",
            "Controls music played in the lobby and menus without muting game audio.",
            menu_music_volume_var,
            menu_music_volume_on_var,
        )

        def current_graphics_settings():
            return {
                "width": width_var.get(),
                "height": height_var.get(),
                "fps": fps_var.get(),
                "render_scale": render_scale_var.get(),
                "fullscreen_mode": mode_names[mode_var.get()],
                "vsync": vsync_var.get(),
                "dynamic_resolution": dynamic_resolution_var.get(),
                "main_volume": round(float(main_volume_var.get())),
                "main_volume_on": main_volume_on_var.get(),
                "menu_music_volume": round(float(menu_music_volume_var.get())),
                "menu_music_volume_on": menu_music_volume_on_var.get(),
                "quality": {
                    key: quality_names[quality_var.get()]
                    for key, quality_var in quality_vars.items()
                },
            }

        preset_shell = SmoothCard(
            outer,
            padding=12,
            radius=16,
            shadow=True,
        )
        preset_shell.pack(fill="x", pady=(0, 10), before=notebook)
        preset_bar = preset_shell.body
        preset_bar.columnconfigure(0, weight=1)
        ttk.Label(
            preset_bar,
            text="SAVED GRAPHICS PRESETS",
            style="FieldLabel.TLabel",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))
        graphics_preset_var = tk.StringVar()
        graphics_preset_combo = ttk.Combobox(
            preset_bar,
            textvariable=graphics_preset_var,
            state="readonly",
            values=sorted(self.manager.graphics_presets(), key=str.casefold),
        )
        graphics_preset_combo.grid(row=1, column=0, sticky="ew")

        def refresh_graphics_presets(selected=None):
            names = sorted(self.manager.graphics_presets(), key=str.casefold)
            graphics_preset_combo["values"] = names
            if selected in names:
                graphics_preset_var.set(selected)
            elif names:
                graphics_preset_var.set(names[0])
            else:
                graphics_preset_var.set("")

        def load_graphics_preset():
            name = graphics_preset_var.get()
            preset = self.manager.graphics_presets().get(name)
            if not preset:
                return
            width_var.set(str(preset["width"]))
            height_var.set(str(preset["height"]))
            fps_var.set(str(preset["fps"]))
            render_scale_var.set(str(preset["render_scale"]))
            mode_var.set(
                next(
                    label
                    for label, mode in mode_names.items()
                    if mode == preset["fullscreen_mode"]
                )
            )
            vsync_var.set(preset["vsync"])
            dynamic_resolution_var.set(preset["dynamic_resolution"])
            main_volume_var.set(str(preset["main_volume"]))
            main_volume_on_var.set(preset["main_volume_on"])
            menu_music_volume_var.set(str(preset["menu_music_volume"]))
            menu_music_volume_on_var.set(preset["menu_music_volume_on"])
            for key, quality_var in quality_vars.items():
                level = preset["quality"][key]
                quality_var.set(
                    next(
                        label
                        for label, value in quality_names.items()
                        if value == level
                    )
                )

        def save_graphics_preset():
            name = simpledialog.askstring(
                "Save Graphics Preset",
                "Preset name:",
                initialvalue=graphics_preset_var.get(),
                parent=dialog,
            )
            if name is None:
                return
            try:
                saved_name = self.manager.save_graphics_preset(
                    name,
                    current_graphics_settings(),
                )
                refresh_graphics_presets(saved_name)
            except ManagerError as exc:
                messagebox.showerror(
                    "Could Not Save Graphics Preset",
                    str(exc),
                    parent=dialog,
                )

        def delete_graphics_preset():
            name = graphics_preset_var.get()
            if not name:
                return
            if not messagebox.askyesno(
                "Delete Graphics Preset",
                f"Delete graphics preset '{name}'?",
                parent=dialog,
            ):
                return
            try:
                self.manager.delete_graphics_preset(name)
                refresh_graphics_presets()
            except ManagerError as exc:
                messagebox.showerror(
                    "Could Not Delete Graphics Preset",
                    str(exc),
                    parent=dialog,
                )

        ttk.Button(
            preset_bar,
            text="Load",
            command=load_graphics_preset,
        ).grid(row=1, column=1, padx=(8, 0))
        ttk.Button(
            preset_bar,
            text="Save As",
            command=save_graphics_preset,
        ).grid(row=1, column=2, padx=(6, 0))
        ttk.Button(
            preset_bar,
            text="Delete",
            command=delete_graphics_preset,
            style="Danger.TButton",
        ).grid(row=1, column=3, padx=(6, 0))
        refresh_graphics_presets()

        buttons = ttk.Frame(outer)
        buttons.pack(
            side="bottom",
            fill="x",
            pady=(12, 0),
            before=notebook,
        )

        def save():
            try:
                backup = self.manager.save_game_settings(
                    settings_file,
                    current_graphics_settings(),
                )
                self._append_output(f"Graphics settings saved. Backup: {backup}\n")
                messagebox.showinfo(
                    "Graphics Settings Saved",
                    f"Settings saved successfully.\n\nBackup:\n{backup}",
                    parent=dialog,
                )
                dialog.destroy()
            except (ManagerError, KeyError) as exc:
                messagebox.showerror(
                    "Could Not Save Graphics Settings",
                    str(exc),
                    parent=dialog,
                )

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Save graphics settings",
            command=save,
            style="Accent.TButton",
        ).pack(side="right", padx=(0, 6))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())

    def login(self):
        account = self.manager.active
        self._run_legendary(
            ["auth"],
            "Signing in to Epic Games",
            on_success=lambda: self._ensure_game_metadata(account),
            account=account,
            auth_client=True,
        )

    def logout(self):
        self._run_legendary(["auth", "--delete"], "Epic Games sign-out")


MODIFIER_FIELDS = {
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "cmd": "cmd",
    "command": "cmd",
}
MODIFIER_LABELS = (
    ("shift", "Shift"),
    ("ctrl", "Ctrl"),
    ("alt", "Alt"),
    ("cmd", "Cmd"),
)


def _preserved_action_data(source):
    source_mappings = source.get("action_mappings")
    if isinstance(source_mappings, dict):
        action_mappings = copy.deepcopy(source_mappings)
    else:
        action_mappings = {
            action: [{"key": key} for key in keys if key]
            for action, keys in source.get("actions", {}).items()
        }
    actions = {}
    for action, mappings in action_mappings.items():
        actions[action] = [
            str(mapping if isinstance(mapping, str) else mapping.get("key", "")).strip()
            for mapping in mappings
            if str(
                mapping if isinstance(mapping, str) else mapping.get("key", "")
            ).strip()
        ]
    return action_mappings, actions


def open_input_settings_dialog(app):
    input_path = app.manager.input_settings_path
    try:
        input_file, data = app.manager.read_input_settings(input_path)
    except ManagerError as exc:
        selected = filedialog.askopenfilename(
            title="Select Input.ini",
            initialdir=str(input_path.parent),
            initialfile="Input.ini",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
            parent=app,
        )
        if not selected:
            messagebox.showerror("Could Not Open Controls", str(exc), parent=app)
            return
        try:
            input_file = app.manager.set_input_settings_path(selected)
            input_file, data = app.manager.read_input_settings(input_file)
        except ManagerError as selected_exc:
            messagebox.showerror(
                "Could Not Open Controls",
                str(selected_exc),
                parent=app,
            )
            return

    dialog = tk.Toplevel(app)
    dialog.title("Controls - Better Together")
    dialog.transient(app)
    dialog.grab_set()
    dialog.geometry("1240x850")
    dialog.minsize(1040, 720)
    dialog.configure(background=COLORS["bg"])
    app._apply_icon_to_window(dialog)

    outer = ttk.Frame(dialog, padding=24)
    outer.pack(fill="both", expand=True)
    app._dialog_header(
        outer,
        "Game controls",
        "Controls",
        "Choose keyboard, mouse, and controller bindings. A backup is created "
        "automatically when you save, and your choices can be reused in launch "
        "presets.",
    )

    active_source = {"data": copy.deepcopy(data)}
    action_vars = {}
    movement_vars = {}
    summary_var = tk.StringVar()
    input_path_var = tk.StringVar(value=str(input_file))
    input_preset_var = tk.StringVar()
    controller_to_key = {label: key for key, label in GAMEPAD_KEY_LABELS.items()}
    controller_options = tuple(GAMEPAD_KEY_LABELS.get(key, key) for key in GAMEPAD_KEYS)

    def mapping_token(mapping, device):
        if isinstance(mapping, str):
            mapping = {"key": mapping}
        key = str(mapping.get("key", "")).strip()
        if not key:
            return ""
        if device == "controller":
            key = GAMEPAD_KEY_LABELS.get(key, key)
        modifiers = [label for field, label in MODIFIER_LABELS if mapping.get(field)]
        return "+".join([*modifiers, key])

    def parse_binding_text(value, device):
        mappings = []
        for token in re.split(r"\s*[;,]\s*", value.strip()):
            token = token.strip()
            if not token:
                continue
            parts = [part.strip() for part in token.split("+") if part.strip()]
            flags = {field: False for field, _label in MODIFIER_LABELS}
            while len(parts) > 1:
                field = MODIFIER_FIELDS.get(parts[0].casefold())
                if not field:
                    break
                flags[field] = True
                parts.pop(0)
            key = "+".join(parts).strip()
            if device == "controller":
                key = controller_to_key.get(key, key)
            if key:
                mappings.append({"key": key, **flags})
        return mappings

    def source_action_mappings(source, action):
        mappings = source.get("action_mappings", {}).get(action)
        if isinstance(mappings, list):
            return mappings
        return [
            {"key": key} for key in source.get("actions", {}).get(action, []) if key
        ]

    def movement_keys(source, binding):
        entries = source.get("axis_mappings", {}).get(binding["axis"], [])
        keys = []
        for mapping in entries:
            try:
                same_scale = (
                    abs(float(mapping.get("scale", 1.0)) - binding["scale"]) < 0.0001
                )
            except (TypeError, ValueError):
                continue
            key = str(mapping.get("key", "")).strip()
            if same_scale and app.manager._device_for_key(key) == "keyboard":
                keys.append(key)
        return keys or [binding["default"]]

    def set_controls(source):
        active_source["data"] = copy.deepcopy(source)
        for action, variables in action_vars.items():
            grouped = {"keyboard": [], "mouse": [], "controller": []}
            for mapping in source_action_mappings(source, action):
                key = str(mapping.get("key", "")).strip()
                device = app.manager._device_for_key(key)
                if device in grouped:
                    token = mapping_token(mapping, device)
                    if token and token not in grouped[device]:
                        grouped[device].append(token)
            for device, variable in variables.items():
                variable.set(" ; ".join(grouped[device]))

        for binding in MOVEMENT_BINDINGS:
            movement_vars[binding["id"]].set(" ; ".join(movement_keys(source, binding)))
        action_count = len(action_vars)
        mapping_count = sum(
            len(source_action_mappings(source, action)) for action in action_vars
        )
        axis_source = source.get("axis_source", "file")
        summary_var.set(
            f"{action_count} actions · {mapping_count} bindings · "
            f"movement from {axis_source}"
        )

    def current_input_data():
        source = active_source["data"]
        action_mappings, actions = _preserved_action_data(source)
        for action, variables in action_vars.items():
            mappings = []
            for device in ("keyboard", "mouse", "controller"):
                mappings.extend(parse_binding_text(variables[device].get(), device))
            seen = set()
            unique = []
            for mapping in mappings:
                signature = (
                    mapping["key"],
                    mapping["shift"],
                    mapping["ctrl"],
                    mapping["alt"],
                    mapping["cmd"],
                )
                if signature not in seen:
                    unique.append(mapping)
                    seen.add(signature)
            action_mappings[action] = unique
            actions[action] = [mapping["key"] for mapping in unique]

        axis_mappings = copy.deepcopy(source.get("axis_mappings", {}))
        for binding in MOVEMENT_BINDINGS:
            entries = axis_mappings.setdefault(binding["axis"], [])
            retained = []
            for mapping in entries:
                try:
                    same_scale = (
                        abs(float(mapping.get("scale", 1.0)) - binding["scale"])
                        < 0.0001
                    )
                except (TypeError, ValueError):
                    same_scale = False
                key = str(mapping.get("key", "")).strip()
                is_keyboard = app.manager._device_for_key(key) == "keyboard"
                if not (same_scale and is_keyboard):
                    retained.append(mapping)

            new_mappings = parse_binding_text(
                movement_vars[binding["id"]].get(),
                "keyboard",
            )
            for mapping in new_mappings:
                key = mapping["key"]
                if app.manager._device_for_key(key) != "keyboard":
                    raise ValueError(
                        f"{binding['role']} {binding['label']} must use a keyboard key."
                    )
                retained.append({"key": key, "scale": binding["scale"]})
            axis_mappings[binding["axis"]] = retained

        return {
            "actions": actions,
            "action_mappings": action_mappings,
            "axis_mappings": axis_mappings,
            "axis_source": "file",
        }

    path_shell = SmoothCard(outer, padding=12, radius=16, shadow=True)
    path_shell.pack(fill="x", pady=(0, 10))
    path_card = path_shell.body
    path_card.columnconfigure(0, weight=1)
    ttk.Label(
        path_card,
        text="CONTROLS FILE (INPUT.INI)",
        style="FieldLabel.TLabel",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    ttk.Entry(path_card, textvariable=input_path_var, state="readonly").grid(
        row=1, column=0, sticky="ew"
    )

    def select_input_file():
        selected = filedialog.askopenfilename(
            title="Select Input.ini",
            initialdir=str(Path(input_path_var.get()).parent),
            initialfile="Input.ini",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
            parent=dialog,
        )
        if not selected:
            return
        try:
            app.manager.set_input_settings_path(selected)
        except ManagerError as exc:
            messagebox.showerror("Could Not Set Input Path", str(exc), parent=dialog)
            return
        messagebox.showinfo(
            "Input Path Saved",
            "The selected path was saved. Reopen Input Settings to load it.",
            parent=dialog,
        )
        dialog.destroy()

    ttk.Button(
        path_card,
        text="Choose file…",
        command=select_input_file,
        style="Compact.TButton",
    ).grid(row=1, column=1, padx=(8, 0))

    preset_shell = SmoothCard(outer, padding=12, radius=16, shadow=True)
    preset_shell.pack(fill="x", pady=(0, 10))
    preset_bar = preset_shell.body
    preset_bar.columnconfigure(0, weight=1)
    ttk.Label(
        preset_bar,
        text="SAVED CONTROL PRESETS",
        style="FieldLabel.TLabel",
    ).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 5))
    input_preset_combo = ttk.Combobox(
        preset_bar,
        textvariable=input_preset_var,
        state="readonly",
    )
    input_preset_combo.grid(row=1, column=0, sticky="ew")

    def refresh_input_presets(selected=None):
        names = sorted(app.manager.input_presets(), key=str.casefold)
        input_preset_combo["values"] = names
        if selected in names:
            input_preset_var.set(selected)
        elif names:
            input_preset_var.set(names[0])
        else:
            input_preset_var.set("")

    def load_input_preset():
        preset = app.manager.input_presets().get(input_preset_var.get())
        if preset:
            set_controls(preset)

    def save_input_preset():
        name = simpledialog.askstring(
            "Save Input Preset",
            "Preset name:",
            initialvalue=input_preset_var.get(),
            parent=dialog,
        )
        if name is None:
            return
        try:
            saved_name = app.manager.save_input_preset(name, current_input_data())
            refresh_input_presets(saved_name)
        except (ManagerError, ValueError) as exc:
            messagebox.showerror("Could Not Save Input Preset", str(exc), parent=dialog)

    def delete_input_preset():
        name = input_preset_var.get()
        if not name:
            return
        if not messagebox.askyesno(
            "Delete Input Preset",
            f"Delete input preset '{name}'?",
            parent=dialog,
        ):
            return
        try:
            app.manager.delete_input_preset(name)
            refresh_input_presets()
        except ManagerError as exc:
            messagebox.showerror(
                "Could Not Delete Input Preset", str(exc), parent=dialog
            )

    def reload_file():
        try:
            _path, source = app.manager.read_input_settings(input_file)
            set_controls(source)
        except ManagerError as exc:
            messagebox.showerror("Could Not Reload Input.ini", str(exc), parent=dialog)

    ttk.Button(preset_bar, text="Load", command=load_input_preset).grid(
        row=1, column=1, padx=(8, 0)
    )
    ttk.Button(preset_bar, text="Save As", command=save_input_preset).grid(
        row=1, column=2, padx=(6, 0)
    )
    ttk.Button(
        preset_bar,
        text="Delete",
        command=delete_input_preset,
        style="Danger.TButton",
    ).grid(row=1, column=3, padx=(6, 0))
    ttk.Button(
        preset_bar,
        text="Reload file",
        command=reload_file,
        style="Compact.TButton",
    ).grid(row=1, column=4, padx=(12, 0))

    guidance_shell = SmoothCard(
        outer,
        padding=(12, 9),
        radius=14,
        shadow=False,
    )
    guidance_shell.pack(fill="x", pady=(0, 10))
    guidance = guidance_shell.body
    ttk.Label(
        guidance,
        text="ONE CONTROLLER MAPPING",
        style="AccentBadge.TLabel",
    ).pack(side="left")
    ttk.Label(
        guidance,
        text=(
            "DBD stores generic Gamepad_* keys, so one controller binding applies "
            "to both Xbox and PlayStation. Use a semicolon for multiple bindings; "
            "modifier combinations such as Shift+F are supported."
        ),
        style="CardText.TLabel",
        wraplength=930,
    ).pack(side="left", padx=(12, 0))

    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True)

    def make_scroll_area(parent):
        canvas = tk.Canvas(
            parent,
            background=COLORS["surface"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, style="CardInner.TFrame")
        frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        def scroll(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", scroll))
        canvas.bind(
            "<Leave>",
            lambda _event: canvas.unbind_all("<MouseWheel>"),
        )
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return frame

    actions_by_category = {category: [] for category, _label in ACTION_CATEGORIES}
    for action in data.get("actions", {}):
        if action in HIDDEN_ACTIONS:
            continue
        metadata = action_metadata(action)
        if metadata["category"] in actions_by_category:
            actions_by_category[metadata["category"]].append(action)
    for actions in actions_by_category.values():
        actions.sort(key=lambda action: action_metadata(action)["label"].casefold())
    survivor_actions = actions_by_category["survivor"]
    if "Interact_Camper" in survivor_actions:
        survivor_actions.remove("Interact_Camper")
        survivor_actions.insert(0, "Interact_Camper")

    tab_specs = list(ACTION_CATEGORIES)
    tab_specs.insert(2, ("movement", "Movement"))
    for category, category_label in tab_specs:
        tab_shell = SmoothCard(
            notebook,
            padding=12,
            radius=16,
            shadow=False,
        )
        tab = tab_shell.body
        if category == "movement":
            notebook.add(tab_shell, text="Movement (8)")
            movement_frame = make_scroll_area(tab)
            movement_frame.columnconfigure(0, weight=1)
            movement_frame.columnconfigure(1, weight=2)
            movement_frame.columnconfigure(2, weight=2)
            ttk.Label(
                movement_frame,
                text="MOVEMENT",
                style="FieldLabel.TLabel",
            ).grid(row=0, column=0, sticky="w", padx=6, pady=(0, 7))
            ttk.Label(
                movement_frame,
                text="KEYBOARD",
                style="FieldLabel.TLabel",
            ).grid(row=0, column=1, sticky="w", padx=6, pady=(0, 7))
            ttk.Label(
                movement_frame,
                text="CONTROLLER",
                style="FieldLabel.TLabel",
            ).grid(row=0, column=2, sticky="w", padx=6, pady=(0, 7))
            row = 1
            last_role = None
            for binding in MOVEMENT_BINDINGS:
                if binding["role"] != last_role:
                    ttk.Label(
                        movement_frame,
                        text=binding["role"].upper(),
                        style="AccentBadge.TLabel",
                    ).grid(
                        row=row,
                        column=0,
                        columnspan=3,
                        sticky="w",
                        padx=6,
                        pady=(8 if row > 1 else 0, 6),
                    )
                    row += 1
                    last_role = binding["role"]
                ttk.Label(
                    movement_frame,
                    text=binding["label"],
                    style="CardText.TLabel",
                ).grid(row=row, column=0, sticky="w", padx=6, pady=5)
                variable = tk.StringVar()
                movement_vars[binding["id"]] = variable
                ttk.Combobox(
                    movement_frame,
                    textvariable=variable,
                    values=KEYBOARD_KEYS,
                ).grid(row=row, column=1, sticky="ew", padx=6, pady=5)
                ttk.Label(
                    movement_frame,
                    text="Left stick (fixed axis mapping)",
                    style="CardMuted.TLabel",
                ).grid(row=row, column=2, sticky="w", padx=6, pady=5)
                row += 1
            continue

        actions = actions_by_category.get(category, [])
        notebook.add(tab_shell, text=f"{category_label} ({len(actions)})")
        actions_frame = make_scroll_area(tab)
        widths = (340, 245, 205, 300)
        headers = (
            "Binding",
            "Keyboard",
            "Mouse",
            "Controller · Xbox / PlayStation",
        )
        for column, (header, width) in enumerate(zip(headers, widths, strict=False)):
            actions_frame.columnconfigure(column, minsize=width, weight=1)
            ttk.Label(
                actions_frame,
                text=header.upper(),
                style="FieldLabel.TLabel",
            ).grid(row=0, column=column, sticky="w", padx=6, pady=(0, 7))

        for row, action in enumerate(actions, start=1):
            metadata = action_metadata(action)
            action_cell = ttk.Frame(actions_frame, style="CardInner.TFrame")
            action_cell.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            ttk.Label(
                action_cell,
                text=metadata["label"],
                style="CardText.TLabel",
            ).pack(anchor="w")
            variables = {
                "keyboard": tk.StringVar(),
                "mouse": tk.StringVar(),
                "controller": tk.StringVar(),
            }
            action_vars[action] = variables
            ttk.Combobox(
                actions_frame,
                textvariable=variables["keyboard"],
                values=KEYBOARD_KEYS,
            ).grid(row=row, column=1, sticky="ew", padx=6, pady=5)
            ttk.Combobox(
                actions_frame,
                textvariable=variables["mouse"],
                values=MOUSE_KEYS,
            ).grid(row=row, column=2, sticky="ew", padx=6, pady=5)
            ttk.Combobox(
                actions_frame,
                textvariable=variables["controller"],
                values=controller_options,
            ).grid(row=row, column=3, sticky="ew", padx=6, pady=5)

    set_controls(data)
    refresh_input_presets()

    footer = ttk.Frame(outer)
    footer.pack(side="bottom", fill="x", pady=(12, 0), before=notebook)
    ttk.Label(
        footer,
        textvariable=summary_var,
        style="Subtitle.TLabel",
    ).pack(side="left")

    def save_to_input_ini():
        try:
            backup = app.manager.save_input_settings(
                input_file,
                current_input_data(),
            )
            app._append_output(f"Input settings saved. Backup: {backup}\n")
            messagebox.showinfo(
                "Input Settings Saved",
                f"Settings saved successfully.\n\nBackup:\n{backup}",
                parent=dialog,
            )
            dialog.destroy()
        except (ManagerError, ValueError) as exc:
            messagebox.showerror(
                "Could Not Save Input Settings", str(exc), parent=dialog
            )

    ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side="right")
    ttk.Button(
        footer,
        text="Save controls",
        command=save_to_input_ini,
        style="Accent.TButton",
    ).pack(side="right", padx=(0, 6))
    dialog.bind("<Escape>", lambda _event: dialog.destroy())
