import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from .constants import APP_DISPLAY_VERSION, APP_NAME, APP_VERSION, DBD_APP_NAME
from .manager import EGSManager, ManagerError
from .runtime import CommandRunner, PresetLauncher
from .settings_dialogs import SettingsDialogMixin
from .ui import (
    COLORS,
    SmoothCard,
    configure_theme,
    enable_window_rounding,
    install_smooth_button_adapter,
    normalize_accent,
    refresh_smooth_widgets,
)

install_smooth_button_adapter()


def _redact_command_arguments(arguments):
    displayed_arguments = []
    redact_next = False
    for argument in arguments:
        if redact_next:
            displayed_arguments.append("<hidden>")
            redact_next = False
            continue
        displayed_arguments.append(str(argument))
        redact_next = argument in {"--code", "--token", "--sid"}
    return displayed_arguments


class EGSApp(SettingsDialogMixin, tk.Tk):
    def __init__(self, manager=None):
        super().__init__()
        self.title(f"{APP_NAME} · v{APP_VERSION}")
        self._set_window_icon()
        self.geometry("1180x860")
        self.minsize(1000, 760)

        self.manager = manager or EGSManager()
        self.command_runner = CommandRunner()
        appearance = self.manager.appearance()
        self.theme_mode = appearance["mode"]
        self.accent_color = appearance["accent"]
        self.output_queue = queue.Queue()
        self.running = False
        self.preset_running = False
        self.on_command_success = None
        self._command_thread = None
        self._preset_thread = None
        self._preset_cancel_event = threading.Event()
        self._closing = False

        self.account_folder_var = tk.StringVar(
            value=str(self.manager.account_folder)
            if self.manager.account_folder
            else ""
        )
        self.account_var = tk.StringVar()
        self.new_account_var = tk.StringVar()
        self.preset_var = tk.StringVar()
        self.dbd_path_var = tk.StringVar(
            value=str(self.manager.dbd_path) if self.manager.dbd_path else ""
        )
        self.skip_version_var = tk.BooleanVar(value=True)
        self.launch_arguments_var = tk.StringVar(value=self.manager.launch_arguments())
        self.status_var = tk.StringVar(value="Ready")
        self.profile_count_var = tk.StringVar(value="0 PROFILES")
        self.preset_count_var = tk.StringVar(value="0 PRESETS")
        self.theme_button_var = tk.StringVar()

        self._configure_style()
        enable_window_rounding(self, dark=self.theme_mode == "dark")
        self._build_ui()
        self.refresh_accounts()
        self.refresh_presets()
        self.protocol("WM_DELETE_WINDOW", self._request_close)
        self.after(100, self._drain_output_queue)

    def _set_window_icon(self):
        self._apply_icon_to_window(self)

    @staticmethod
    def _apply_icon_to_window(window):
        base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        icon_path = base_path / "icon.ico"
        if icon_path.exists():
            try:
                window.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass
        background = COLORS.get("bg", "#FFFFFF").lstrip("#")
        dark = sum(int(background[index : index + 2], 16) for index in (0, 2, 4)) < 384
        enable_window_rounding(window, dark=dark)

    def _configure_style(self):
        self.style = configure_theme(
            self,
            mode=self.theme_mode,
            accent=self.accent_color,
        )
        self._update_theme_button_text()

    def _update_theme_button_text(self):
        self.theme_button_var.set(
            "White mode" if self.theme_mode == "dark" else "Dark mode"
        )

    def _apply_appearance(self, mode, accent, persist=True):
        mode = "light" if mode == "light" else "dark"
        accent = normalize_accent(accent)
        if persist:
            try:
                self.manager.set_appearance(mode, accent)
            except (ManagerError, OSError) as exc:
                messagebox.showerror("Could Not Save Appearance", str(exc))
                return

        self.theme_mode = mode
        self.accent_color = accent
        self.style = configure_theme(self, mode=mode, accent=accent)
        self._update_theme_button_text()
        refresh_smooth_widgets(self)
        enable_window_rounding(self, dark=mode == "dark")

        if hasattr(self, "accent_bar"):
            self.accent_bar.configure(background=COLORS["accent"])
        if hasattr(self, "output"):
            self.output.configure(
                background=COLORS["console"],
                foreground=COLORS["console_text"],
                insertbackground=COLORS["text"],
                selectbackground=COLORS["accent_pressed"],
                selectforeground=COLORS["accent_text"],
            )
        if hasattr(self, "status_dot"):
            self.status_dot.configure(background=COLORS["bg"])
            self._set_status()

    def _toggle_theme(self):
        mode = "light" if self.theme_mode == "dark" else "dark"
        self._apply_appearance(mode, self.accent_color)

    def _choose_accent_color(self):
        _rgb, selected = colorchooser.askcolor(
            color=self.accent_color,
            title="Choose Accent Color",
            parent=self,
        )
        if selected:
            self._apply_appearance(self.theme_mode, selected)

    def _create_card(self, parent, title, subtitle, badge_var=None):
        card = SmoothCard(parent, padding=18, radius=18, shadow=True)
        surface = card.body
        header = ttk.Frame(surface, style="CardInner.TFrame")
        header.pack(fill="x")
        title_block = ttk.Frame(header, style="CardInner.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_block,
            text=title,
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            title_block,
            text=subtitle,
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        if badge_var is not None:
            ttk.Label(
                header,
                textvariable=badge_var,
                style="Badge.TLabel",
            ).pack(side="right", padx=(12, 0))
        ttk.Separator(surface).pack(fill="x", pady=(14, 15))
        body = ttk.Frame(surface, style="CardInner.TFrame")
        body.pack(fill="both", expand=True)
        return card, body

    def _dialog_header(self, parent, eyebrow, title, description):
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text=eyebrow.upper(), style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(header, text=title, style="Title.TLabel").pack(
            anchor="w", pady=(2, 3)
        )
        ttk.Label(
            header,
            text=description,
            style="Subtitle.TLabel",
            wraplength=720,
        ).pack(anchor="w")

    def _clear_output(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _style_listbox(self, listbox):
        listbox.configure(
            background=COLORS["input"],
            foreground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["accent_text"],
            disabledforeground=COLORS["subtle"],
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border_focus"],
            highlightthickness=1,
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 10),
        )

    def _build_ui(self):
        root = ttk.Frame(self, style="App.TFrame", padding=(24, 18, 24, 14))
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=5)
        root.rowconfigure(2, weight=2)

        header = ttk.Frame(root, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(1, weight=1)
        self.accent_bar = tk.Frame(
            header,
            background=COLORS["accent"],
            width=5,
            height=54,
        )
        self.accent_bar.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        self.accent_bar.grid_propagate(False)

        brand = ttk.Frame(header, style="App.TFrame")
        brand.grid(row=0, column=1, sticky="w")
        ttk.Label(
            brand,
            text="BETTER TOGETHER",
            style="Eyebrow.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            brand,
            text="Dead by Daylight Launcher",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            brand,
            text="Profiles, group launches, and game settings in one place.",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        header_meta = ttk.Frame(header, style="App.TFrame")
        header_meta.grid(row=0, column=2, sticky="e")
        badges = ttk.Frame(header_meta, style="App.TFrame")
        badges.pack(anchor="e")
        ttk.Label(
            badges,
            textvariable=self.profile_count_var,
            style="Badge.TLabel",
        ).pack(side="left")
        ttk.Label(
            badges,
            textvariable=self.preset_count_var,
            style="Badge.TLabel",
        ).pack(side="left", padx=(8, 0))
        appearance_controls = ttk.Frame(header_meta, style="App.TFrame")
        appearance_controls.pack(anchor="e", pady=(7, 0))
        ttk.Label(
            appearance_controls,
            text=f"v{APP_DISPLAY_VERSION}",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            appearance_controls,
            textvariable=self.theme_button_var,
            command=self._toggle_theme,
            style="Compact.TButton",
        ).pack(side="left")
        ttk.Button(
            appearance_controls,
            text="Accent…",
            command=self._choose_accent_color,
            style="AccentCompact.TButton",
        ).pack(side="left", padx=(6, 0))

        content = ttk.Frame(root, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=6, uniform="content")
        content.columnconfigure(1, weight=5, uniform="content")
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=2)

        library, library_body = self._create_card(
            content,
            "Profile library",
            "Manage saved Epic sessions and choose the active profile.",
            self.profile_count_var,
        )
        library.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        library_body.columnconfigure(0, weight=1)

        ttk.Label(
            library_body,
            text="PROFILE STORAGE FOLDER",
            style="FieldLabel.TLabel",
        ).grid(row=0, column=0, sticky="w")
        folder_row = ttk.Frame(library_body, style="CardInner.TFrame")
        folder_row.grid(row=1, column=0, sticky="ew", pady=(5, 15))
        folder_row.columnconfigure(0, weight=1)
        ttk.Entry(
            folder_row,
            textvariable=self.account_folder_var,
            state="readonly",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            folder_row,
            text="Browse…",
            command=self.select_account_folder,
            style="Compact.TButton",
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(
            library_body,
            text="ACTIVE PROFILE",
            style="FieldLabel.TLabel",
        ).grid(row=2, column=0, sticky="w")
        active_row = ttk.Frame(library_body, style="CardInner.TFrame")
        active_row.grid(row=3, column=0, sticky="ew", pady=(5, 15))
        active_row.columnconfigure(0, weight=1)
        self.account_combo = ttk.Combobox(
            active_row,
            textvariable=self.account_var,
            state="readonly",
        )
        self.account_combo.grid(row=0, column=0, sticky="ew")
        self.account_combo.bind("<<ComboboxSelected>>", self._select_account)
        ttk.Button(
            active_row,
            text="Refresh",
            command=self.refresh_accounts,
            style="Compact.TButton",
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(
            library_body,
            text="CREATE A PROFILE",
            style="FieldLabel.TLabel",
        ).grid(row=4, column=0, sticky="w")
        create_row = ttk.Frame(library_body, style="CardInner.TFrame")
        create_row.grid(row=5, column=0, sticky="ew", pady=(5, 14))
        create_row.columnconfigure(0, weight=1)
        new_profile_entry = ttk.Entry(
            create_row,
            textvariable=self.new_account_var,
        )
        new_profile_entry.grid(row=0, column=0, sticky="ew")
        new_profile_entry.bind("<Return>", lambda _event: self.create_account())
        ttk.Button(
            create_row,
            text="Create profile",
            command=self.create_account,
            style="Accent.TButton",
        ).grid(row=0, column=1, padx=(8, 0))

        profile_actions = ttk.Frame(library_body, style="CardInner.TFrame")
        profile_actions.grid(row=6, column=0, sticky="ew", pady=(1, 0))
        for column in range(2):
            profile_actions.columnconfigure(column, weight=1)
        ttk.Button(
            profile_actions,
            text="Export selected",
            command=self.export_account,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            profile_actions,
            text="Delete profile",
            command=self.remove_account,
            style="Danger.TButton",
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        launch, launch_body = self._create_card(
            content,
            "Launch center",
            "Start one profile or orchestrate a saved launch sequence.",
        )
        launch.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
        launch_body.columnconfigure(0, weight=1)

        ttk.Label(
            launch_body,
            text="LAUNCH PRESET",
            style="FieldLabel.TLabel",
        ).grid(row=0, column=0, sticky="w")
        preset_row = ttk.Frame(launch_body, style="CardInner.TFrame")
        preset_row.grid(row=1, column=0, sticky="ew", pady=(5, 8))
        preset_row.columnconfigure(0, weight=1)
        self.preset_combo = ttk.Combobox(
            preset_row,
            textvariable=self.preset_var,
            state="readonly",
        )
        self.preset_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(
            preset_row,
            text="Launch group",
            command=self.launch_preset,
            style="Accent.TButton",
        ).grid(row=0, column=1, padx=(8, 0))

        preset_actions = ttk.Frame(launch_body, style="CardInner.TFrame")
        preset_actions.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        for column in range(3):
            preset_actions.columnconfigure(column, weight=1)
        ttk.Button(
            preset_actions,
            text="New preset",
            command=self.new_preset,
            style="Compact.TButton",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            preset_actions,
            text="Edit",
            command=self.edit_preset,
            style="Compact.TButton",
        ).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(
            preset_actions,
            text="Delete",
            command=self.delete_preset,
            style="Danger.TButton",
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        ttk.Separator(launch_body).grid(row=3, column=0, sticky="ew", pady=(0, 14))
        installation_header = ttk.Frame(launch_body, style="CardInner.TFrame")
        installation_header.grid(row=4, column=0, sticky="ew")
        ttk.Label(
            installation_header,
            text="GAME INSTALLATION",
            style="FieldLabel.TLabel",
        ).pack(side="left")
        ttk.Checkbutton(
            installation_header,
            text="Skip game update check",
            variable=self.skip_version_var,
            style="Card.TCheckbutton",
        ).pack(side="right")
        game_path_row = ttk.Frame(launch_body, style="CardInner.TFrame")
        game_path_row.grid(row=5, column=0, sticky="ew", pady=(5, 8))
        game_path_row.columnconfigure(0, weight=1)
        ttk.Entry(
            game_path_row,
            textvariable=self.dbd_path_var,
            state="readonly",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            game_path_row,
            text="Browse…",
            command=self.select_dbd_path,
            style="Compact.TButton",
        ).grid(row=0, column=1, padx=(8, 0))

        game_tools = ttk.Frame(launch_body, style="CardInner.TFrame")
        game_tools.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        for column in range(2):
            game_tools.columnconfigure(column, weight=1)
        ttk.Button(
            game_tools,
            text="Set up all profiles",
            command=self.sync_dbd_profiles,
            style="Compact.TButton",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            game_tools,
            text="Update game",
            command=self.install_game,
            style="Compact.TButton",
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        launch_arguments_row = ttk.Frame(launch_body, style="CardInner.TFrame")
        launch_arguments_row.grid(row=7, column=0, sticky="ew", pady=(0, 13))
        launch_arguments_row.columnconfigure(1, weight=1)
        ttk.Label(
            launch_arguments_row,
            text="ADVANCED LAUNCH OPTIONS",
            style="FieldLabel.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(
            launch_arguments_row,
            textvariable=self.launch_arguments_var,
        ).grid(row=0, column=1, sticky="ew")
        ttk.Label(
            launch_body,
            text=(
                "Optional; use quotes for a value containing spaces. "
                "Applies to all launches."
            ),
            style="CardMuted.TLabel",
        ).grid(row=8, column=0, sticky="w", pady=(0, 10))

        ttk.Button(
            launch_body,
            text="Launch Dead by Daylight",
            command=self.launch_game,
            style="Launch.TButton",
        ).grid(row=9, column=0, sticky="ew")

        console_card = SmoothCard(root, padding=16, radius=18, shadow=True)
        console_card.grid(row=2, column=0, sticky="nsew", pady=(16, 0))
        console = console_card.body
        console.columnconfigure(0, weight=1)
        console.rowconfigure(2, weight=1)
        console_header = ttk.Frame(console, style="CardInner.TFrame")
        console_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        console_header.columnconfigure(0, weight=1)
        console_title = ttk.Frame(console_header, style="CardInner.TFrame")
        console_title.grid(row=0, column=0, sticky="w")
        ttk.Label(
            console_title,
            text="Activity",
            style="CardTitle.TLabel",
        ).pack(side="left")
        ttk.Label(
            console_title,
            text="RECENT ACTIVITY",
            style="AccentBadge.TLabel",
        ).pack(side="left", padx=(10, 0))

        console_tools = ttk.Frame(console_header, style="CardInner.TFrame")
        console_tools.grid(row=0, column=1, sticky="e")
        ttk.Button(
            console_tools,
            text="Sign in to Epic Games",
            command=self.login,
            style="Compact.TButton",
        ).pack(side="left")
        ttk.Button(
            console_tools,
            text="Sign out",
            command=self.logout,
            style="Compact.TButton",
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            console_tools,
            text="Graphics & sound",
            command=self.open_graphics_settings,
            style="Compact.TButton",
        ).pack(side="left", padx=(12, 0))
        ttk.Button(
            console_tools,
            text="Controls",
            command=self.open_input_settings,
            style="Compact.TButton",
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            console_tools,
            text="Clear",
            command=self._clear_output,
            style="Compact.TButton",
        ).pack(side="left", padx=(12, 0))

        ttk.Separator(console).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 10),
        )
        output_wrap = ttk.Frame(console, style="CardInner.TFrame")
        output_wrap.grid(row=2, column=0, columnspan=2, sticky="nsew")
        output_wrap.columnconfigure(0, weight=1)
        output_wrap.rowconfigure(0, weight=1)
        self.output = tk.Text(
            output_wrap,
            wrap="word",
            height=4,
            font=("Cascadia Mono", 9),
            state="disabled",
            background=COLORS["console"],
            foreground=COLORS["console_text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent_pressed"],
            selectforeground=COLORS["accent_text"],
            borderwidth=0,
            relief="flat",
            padx=12,
            pady=10,
        )
        self.output.grid(row=0, column=0, sticky="nsew")
        output_scroll = ttk.Scrollbar(
            output_wrap,
            orient="vertical",
            command=self.output.yview,
        )
        output_scroll.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=output_scroll.set)

        status = ttk.Frame(root, style="App.TFrame")
        status.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.status_dot = tk.Label(
            status,
            text="●",
            background=COLORS["bg"],
            foreground=COLORS["success"],
            font=("Segoe UI", 8),
        )
        self.status_dot.pack(side="left")
        ttk.Label(status, textvariable=self.status_var, style="Subtitle.TLabel").pack(
            side="left", padx=(7, 0)
        )
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=180)
        self.progress.pack(side="right")

    def refresh_accounts(self, selected=None):
        accounts = self.manager.accounts()
        self.account_combo["values"] = accounts
        self.profile_count_var.set(
            f"{len(accounts)} PROFILE{'S' if len(accounts) != 1 else ''}"
        )
        preferred = selected or self.manager.active
        if preferred in accounts:
            self.account_var.set(preferred)
        elif accounts:
            self.account_var.set(accounts[0])
            self.manager.set_active(accounts[0])
        else:
            self.account_var.set("")
        self.refresh_presets()
        self._set_status()

    def refresh_presets(self, selected=None):
        if not hasattr(self, "preset_combo"):
            return
        names = sorted(self.manager.presets(), key=str.casefold)
        self.preset_combo["values"] = names
        self.preset_count_var.set(
            f"{len(names)} PRESET{'S' if len(names) != 1 else ''}"
        )
        preferred = selected or self.preset_var.get()
        if preferred in names:
            self.preset_var.set(preferred)
        elif names:
            self.preset_var.set(names[0])
        else:
            self.preset_var.set("")

    def _set_status(self, text=None):
        if text:
            self.status_var.set(text)
        elif not self.manager.account_folder:
            self.status_var.set("Select an account folder")
        elif self.manager.active:
            self.status_var.set(f"Active profile: {self.manager.active}")
        else:
            self.status_var.set("No profile configured")
        if hasattr(self, "status_dot"):
            ready = bool(self.manager.account_folder and self.manager.active)
            self.status_dot.configure(
                foreground=COLORS["success"] if ready else COLORS["warning"]
            )

    def select_account_folder(self):
        initial_dir = self.manager.account_folder or Path.home()
        path = filedialog.askdirectory(
            title="Choose Profile Storage Folder",
            initialdir=str(initial_dir),
            mustexist=False,
        )
        if not path:
            return
        try:
            account_folder = self.manager.set_account_folder(path)
            self.account_folder_var.set(str(account_folder))
            self.refresh_accounts()
            self._append_output(f"Account folder: {account_folder}\n")
        except (ManagerError, OSError) as exc:
            messagebox.showerror("Could Not Set Account Folder", str(exc))

    def _select_account(self, _event=None):
        try:
            self.manager.set_active(self.account_var.get())
            self._set_status()
            self._append_output(f"Active profile: {self.manager.active}\n")
        except ManagerError as exc:
            messagebox.showerror("Could Not Select Profile", str(exc))

    def create_account(self):
        try:
            name = self.manager.create_account(self.new_account_var.get())
            self.manager.set_active(name)
            self.new_account_var.set("")
            self.refresh_accounts(name)
            self._append_output(f"Profile '{name}' was created.\n")
        except ManagerError as exc:
            messagebox.showerror("Could Not Create Profile", str(exc))

    def remove_account(self):
        name = self.account_var.get()
        if not name:
            messagebox.showinfo("Delete Profile", "No profile is selected.")
            return
        if not messagebox.askyesno(
            "Delete Profile",
            f"Delete profile '{name}' including its login data?",
        ):
            return
        try:
            self.manager.remove_account(name)
            self.refresh_accounts()
            self._append_output(f"Profile '{name}' was deleted.\n")
        except ManagerError as exc:
            messagebox.showerror("Could Not Delete Profile", str(exc))

    def export_account(self):
        name = self.account_var.get()
        if not name:
            messagebox.showinfo("Export Account", "No profile is selected.")
            return
        if not messagebox.askyesno(
            "Export Sensitive Account Data",
            "This export contains Epic authentication tokens. Anyone with the "
            "file may be able to access this Epic account.\n\n"
            f"Export profile '{name}' anyway?",
            icon="warning",
        ):
            return

        destination = filedialog.asksaveasfilename(
            title="Export Epic Profile",
            initialfile=f"{name}-dbd-account.zip",
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
        )
        if not destination:
            return
        try:
            exported_file = self.manager.export_account(name, destination)
            self._append_output(f"Profile '{name}' exported to {exported_file}.\n")
            messagebox.showinfo(
                "Account Exported",
                "The account ZIP was created successfully. Share it only with "
                "someone you trust.",
            )
        except ManagerError as exc:
            messagebox.showerror("Could Not Export Account", str(exc))

    def new_preset(self):
        self._open_preset_editor()

    def edit_preset(self):
        name = self.preset_var.get()
        if not name:
            messagebox.showinfo("Edit Preset", "No preset is selected.")
            return
        self._open_preset_editor(name)

    def _open_preset_editor(self, preset_name=None):
        accounts = self.manager.accounts()
        if not accounts:
            messagebox.showinfo(
                "Create Preset",
                "Select an account folder containing profiles first.",
            )
            return

        existing = self.manager.presets().get(preset_name, {})
        existing_entries = existing.get("entries")
        if not isinstance(existing_entries, list):
            existing_entries = [
                {"account": account, "graphics_preset": None, "input_preset": None}
                for account in existing.get("accounts", [])
            ]
        entry_items = [
            {
                "account": entry.get("account"),
                "graphics_preset": entry.get("graphics_preset") or None,
                "input_preset": entry.get("input_preset") or None,
            }
            for entry in existing_entries
            if isinstance(entry, dict) and entry.get("account") in accounts
        ]
        graphics_names = sorted(self.manager.graphics_presets(), key=str.casefold)
        input_names = sorted(self.manager.input_presets(), key=str.casefold)

        dialog = tk.Toplevel(self)
        dialog.title("Edit Launch Preset" if preset_name else "New Launch Preset")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("900x650")
        dialog.minsize(780, 580)
        dialog.configure(background=COLORS["bg"])
        self._apply_icon_to_window(dialog)

        outer = ttk.Frame(dialog, padding=24)
        outer.pack(fill="both", expand=True)
        self._dialog_header(
            outer,
            "Launch automation",
            "Edit launch preset" if preset_name else "Create launch preset",
            "Choose profiles, assign per-profile settings, and control launch order.",
        )
        card = SmoothCard(outer, padding=18, radius=18, shadow=True)
        card.pack(fill="both", expand=True)
        frame = card.body
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.rowconfigure(4, weight=1)
        ttk.Label(
            frame,
            text="PRESET NAME",
            style="FieldLabel.TLabel",
        ).grid(row=0, column=0, sticky="w")
        name_var = tk.StringVar(value=preset_name or "")
        name_entry = ttk.Entry(frame, textvariable=name_var, width=38)
        name_entry.grid(
            row=0,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(12, 0),
        )

        ttk.Label(frame, text="AVAILABLE PROFILE", style="FieldLabel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(18, 5)
        )
        ttk.Label(frame, text="GRAPHICS PRESET", style="FieldLabel.TLabel").grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(18, 5)
        )
        ttk.Label(frame, text="INPUT PRESET", style="FieldLabel.TLabel").grid(
            row=1, column=2, sticky="w", padx=(8, 0), pady=(18, 5)
        )
        available_var = tk.StringVar()
        available_combo = ttk.Combobox(
            frame,
            textvariable=available_var,
            state="readonly",
            values=accounts,
            width=38,
        )
        available_combo.grid(row=2, column=0, sticky="ew")
        if accounts:
            available_var.set(accounts[0])
        graphics_var = tk.StringVar(value="Current settings")
        graphics_combo = ttk.Combobox(
            frame,
            textvariable=graphics_var,
            state="readonly",
            values=["Current settings", *graphics_names],
            width=24,
        )
        graphics_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0))
        input_var = tk.StringVar(value="Current settings")
        input_combo = ttk.Combobox(
            frame,
            textvariable=input_var,
            state="readonly",
            values=["Current settings", *input_names],
            width=24,
        )
        input_combo.grid(row=2, column=2, sticky="ew", padx=(8, 0))

        ttk.Label(
            frame,
            text="PROFILES TO LAUNCH · DRAG ORDER WITH THE CONTROLS BELOW",
            style="FieldLabel.TLabel",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(18, 5))
        account_list = tk.Listbox(
            frame,
            selectmode="browse",
            exportselection=False,
            height=min(9, max(5, len(accounts))),
            width=48,
        )
        self._style_listbox(account_list)
        account_list.grid(row=4, column=0, columnspan=3, sticky="nsew")

        def refresh_entry_list(selected_index=None):
            account_list.delete(0, "end")
            for entry in entry_items:
                graphics_name = entry["graphics_preset"] or "Current settings"
                input_name = entry["input_preset"] or "Current settings"
                account_list.insert(
                    "end",
                    f"{entry['account']}  -  Graphics: {graphics_name}  -  "
                    f"Controls: {input_name}",
                )
            if selected_index is not None and entry_items:
                selected_index = max(0, min(selected_index, len(entry_items) - 1))
                account_list.selection_set(selected_index)
                account_list.activate(selected_index)

        refresh_entry_list()

        order_buttons = ttk.Frame(frame, style="CardInner.TFrame")
        order_buttons.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        def add_account():
            account = available_var.get()
            if account and account not in {entry["account"] for entry in entry_items}:
                graphics_preset = graphics_var.get()
                entry_items.append(
                    {
                        "account": account,
                        "graphics_preset": (
                            None
                            if graphics_preset == "Current settings"
                            else graphics_preset
                        ),
                        "input_preset": (
                            None
                            if input_var.get() == "Current settings"
                            else input_var.get()
                        ),
                    }
                )
                refresh_entry_list(len(entry_items) - 1)

        def remove_account():
            selection = account_list.curselection()
            if selection:
                del entry_items[selection[0]]
                refresh_entry_list(selection[0])

        def set_graphics_preset():
            selection = account_list.curselection()
            if not selection:
                return
            graphics_preset = graphics_var.get()
            entry_items[selection[0]]["graphics_preset"] = (
                None if graphics_preset == "Current settings" else graphics_preset
            )
            refresh_entry_list(selection[0])

        def set_input_preset():
            selection = account_list.curselection()
            if not selection:
                return
            preset = input_var.get()
            entry_items[selection[0]]["input_preset"] = (
                None if preset == "Current settings" else preset
            )
            refresh_entry_list(selection[0])

        def move_selected(direction):
            selection = list(account_list.curselection())
            if len(selection) != 1:
                return
            index = selection[0]
            target = index + direction
            if target < 0 or target >= account_list.size():
                return
            entry_items[index], entry_items[target] = (
                entry_items[target],
                entry_items[index],
            )
            refresh_entry_list(target)

        ttk.Button(
            order_buttons,
            text="Add profile",
            command=add_account,
            style="Accent.TButton",
        ).pack(side="left")
        ttk.Button(
            order_buttons,
            text="Remove",
            command=remove_account,
            style="Danger.TButton",
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            order_buttons,
            text="Set Graphics",
            command=set_graphics_preset,
            style="Compact.TButton",
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            order_buttons,
            text="Set Input",
            command=set_input_preset,
            style="Compact.TButton",
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            order_buttons,
            text="Move up",
            command=lambda: move_selected(-1),
            style="Compact.TButton",
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            order_buttons,
            text="Move down",
            command=lambda: move_selected(1),
            style="Compact.TButton",
        ).pack(side="left", padx=(6, 0))

        ttk.Label(
            frame,
            text="DELAY BETWEEN LAUNCHES",
            style="FieldLabel.TLabel",
        ).grid(row=6, column=0, sticky="w", pady=(16, 0))
        delay_var = tk.StringVar(value=str(existing.get("delay_seconds", 20)))
        delay_frame = ttk.Frame(frame, style="CardInner.TFrame")
        delay_frame.grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(12, 0))
        ttk.Spinbox(
            delay_frame,
            from_=0,
            to=3600,
            textvariable=delay_var,
            width=8,
        ).pack(side="left")
        ttk.Label(
            delay_frame,
            text="seconds",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(6, 0))

        buttons = ttk.Frame(frame, style="CardInner.TFrame")
        buttons.grid(row=7, column=0, columnspan=3, sticky="e", pady=(16, 0))

        def save():
            try:
                new_name = self.manager.save_preset(
                    name_var.get(),
                    entry_items,
                    delay_var.get(),
                )
                if preset_name and preset_name != new_name:
                    self.manager.delete_preset(preset_name)
                self.refresh_presets(new_name)
                dialog.destroy()
            except ManagerError as exc:
                messagebox.showerror("Could Not Save Preset", str(exc), parent=dialog)

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")
        ttk.Button(
            buttons,
            text="Save preset",
            command=save,
            style="Accent.TButton",
        ).pack(side="left", padx=(6, 0))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        name_entry.focus_set()

    def delete_preset(self):
        name = self.preset_var.get()
        if not name:
            messagebox.showinfo("Delete Preset", "No preset is selected.")
            return
        if not messagebox.askyesno(
            "Delete Preset",
            f"Delete launch preset '{name}'?",
        ):
            return
        try:
            self.manager.delete_preset(name)
            self.refresh_presets()
        except ManagerError as exc:
            messagebox.showerror("Could Not Delete Preset", str(exc))

    def launch_preset(self):
        name = self.preset_var.get()
        if not name:
            messagebox.showinfo("Launch Preset", "No preset is selected.")
            return
        if self.running or self.preset_running:
            messagebox.showinfo(
                "Operation in Progress",
                "Please wait for the current operation to finish.",
            )
            return

        preset = self.manager.presets().get(name)
        if not isinstance(preset, dict):
            messagebox.showerror("Could Not Launch Preset", "The preset is invalid.")
            return
        entries = preset.get("entries")
        if not isinstance(entries, list):
            entries = [
                {"account": account, "graphics_preset": None, "input_preset": None}
                for account in preset.get("accounts", [])
            ]
        delay_seconds = preset.get("delay_seconds", 20)
        if not entries:
            messagebox.showerror(
                "Could Not Launch Preset",
                "The preset does not contain any profiles.",
            )
            return
        accounts = [
            entry.get("account")
            for entry in entries
            if isinstance(entry, dict) and entry.get("account")
        ]
        if len(accounts) != len(entries):
            messagebox.showerror(
                "Could Not Launch Preset",
                "The preset contains an invalid profile entry.",
            )
            return
        available = set(self.manager.accounts())
        missing = [account for account in accounts if account not in available]
        if missing:
            messagebox.showerror(
                "Could Not Launch Preset",
                "These profiles are missing from the selected account folder: "
                + ", ".join(missing),
            )
            return
        available_graphics = self.manager.graphics_presets()
        missing_graphics = [
            entry.get("graphics_preset")
            for entry in entries
            if entry.get("graphics_preset")
            and entry.get("graphics_preset") not in available_graphics
        ]
        if missing_graphics:
            messagebox.showerror(
                "Could Not Launch Preset",
                "These graphics presets are missing: "
                + ", ".join(dict.fromkeys(missing_graphics)),
            )
            return
        available_inputs = self.manager.input_presets()
        missing_inputs = [
            entry.get("input_preset")
            for entry in entries
            if entry.get("input_preset")
            and entry.get("input_preset") not in available_inputs
        ]
        if missing_inputs:
            messagebox.showerror(
                "Could Not Launch Preset",
                "These input presets are missing: "
                + ", ".join(dict.fromkeys(missing_inputs)),
            )
            return

        try:
            for account in accounts:
                self.manager.sync_dbd_installation(accounts=[account])
            delay_seconds = int(delay_seconds)
            if not 0 <= delay_seconds <= 3600:
                raise ManagerError(
                    "The launch delay must be between 0 and 3600 seconds."
                )
            launch_arguments = self.manager.set_launch_arguments(
                self.launch_arguments_var.get()
            )
        except (ManagerError, TypeError, ValueError) as exc:
            messagebox.showerror("Could Not Launch Preset", str(exc))
            return

        self.preset_running = True
        self._preset_cancel_event.clear()
        self.progress.start(12)
        self._append_output(
            f"\nLaunching preset '{name}': {', '.join(accounts)} "
            f"({delay_seconds}s delay)\n"
        )
        self._preset_thread = threading.Thread(
            target=self._preset_worker,
            args=(
                name,
                entries,
                delay_seconds,
                self.skip_version_var.get(),
                launch_arguments,
            ),
            daemon=True,
        )
        self._preset_thread.start()

    def _preset_worker(
        self,
        name,
        entries,
        delay_seconds,
        skip_version_check,
        launch_arguments,
    ):
        try:
            launcher = PresetLauncher(
                self.manager,
                self.command_runner,
                lambda event, value: self.output_queue.put((f"preset_{event}", value)),
                cancelled=self._preset_cancel_event.is_set,
            )
            launcher.run(
                entries,
                delay_seconds,
                skip_version_check,
                self.manager.parse_launch_arguments(launch_arguments),
            )
            self.output_queue.put(("preset_done", name))
        except (ManagerError, OSError, KeyError) as exc:
            self.output_queue.put(("preset_error", str(exc)))

    def select_dbd_path(self):
        initial_dir = self.manager.dbd_path or Path.home()
        path = filedialog.askdirectory(
            title="Select Dead by Daylight Installation Folder",
            initialdir=str(initial_dir),
        )
        if not path:
            return
        try:
            game_path = self.manager.set_dbd_path(path)
            self.dbd_path_var.set(str(game_path))
            if self.manager.has_dbd_template():
                count = self.manager.sync_dbd_installation()
                self._append_output(
                    f"Dead by Daylight folder synced to {count} profile(s).\n"
                )
                self._set_status("Dead by Daylight folder saved")
            else:
                self._run_legendary(
                    [
                        "import",
                        DBD_APP_NAME,
                        str(game_path),
                        "--disable-check",
                        "--skip-dlcs",
                    ],
                    "Importing Dead by Daylight",
                    on_success=self._finish_first_dbd_import,
                )
        except ManagerError as exc:
            messagebox.showerror("Could Not Set Game Folder", str(exc))

    def _finish_first_dbd_import(self):
        try:
            count = self.manager.sync_dbd_installation()
            self._append_output(
                f"Dead by Daylight folder synced to {count} profile(s).\n"
            )
            messagebox.showinfo(
                "Dead by Daylight Ready",
                f"The installation folder is now configured for {count} profile(s).",
            )
        except ManagerError as exc:
            messagebox.showerror("Could Not Sync Profiles", str(exc))

    def sync_dbd_profiles(self):
        try:
            count = self.manager.sync_dbd_installation()
            self._append_output(
                f"Dead by Daylight folder synced to {count} profile(s).\n"
            )
            self._set_status(f"Synced {count} profile(s)")
        except ManagerError as exc:
            messagebox.showerror("Could Not Sync Profiles", str(exc))

    def launch_game(self):
        try:
            if not self.manager.active:
                raise ManagerError("Please select an active profile first.")
            account = self.manager.active
            launch_arguments = self.manager.set_launch_arguments(
                self.launch_arguments_var.get()
            )
            parsed_arguments = self.manager.parse_launch_arguments(launch_arguments)
            skip_version_check = self.skip_version_var.get()
            self._ensure_game_metadata(
                account,
                on_ready=lambda: self._launch_game_ready(
                    account,
                    parsed_arguments,
                    skip_version_check,
                ),
            )
        except ManagerError as exc:
            messagebox.showerror("Could Not Launch Dead by Daylight", str(exc))

    def _launch_game_ready(self, account, launch_arguments, skip_version_check):
        try:
            self.manager.sync_dbd_installation(accounts=[account])
            arguments = ["launch", DBD_APP_NAME]
            if skip_version_check:
                arguments.append("--skip-version-check")
            arguments.extend(launch_arguments)
            self._run_legendary(
                arguments,
                "Launching Dead by Daylight",
                splash_profile=account,
                account=account,
            )
        except ManagerError as exc:
            messagebox.showerror("Could Not Launch Dead by Daylight", str(exc))

    def _ensure_game_metadata(self, account, on_ready=None):
        """Refresh a profile once when Legendary's required catalog data is absent."""

        if self.manager.has_game_metadata(account):
            if on_ready:
                on_ready()
            return
        self._append_output(
            f"Preparing Epic game data for '{account}' (first launch only).\n"
        )
        self._run_legendary(
            ["status", "--json"],
            "Preparing Epic game data",
            on_success=lambda: self._finish_metadata_refresh(account, on_ready),
            account=account,
        )

    def _finish_metadata_refresh(self, account, on_ready):
        if not self.manager.has_game_metadata(account):
            messagebox.showerror(
                "Dead by Daylight Not Found",
                f"Dead by Daylight was not found in the Epic library for '{account}'.",
            )
            return
        self._append_output(f"Epic game data is ready for '{account}'.\n")
        if on_ready:
            on_ready()

    def install_game(self):
        try:
            if not self.manager.active:
                raise ManagerError("Please select an active profile first.")
            self.manager.sync_dbd_installation(accounts=[self.manager.active])
            self._run_legendary(
                ["install", DBD_APP_NAME, "--skip-dlcs"],
                "Dead by Daylight update in progress",
            )
        except ManagerError as exc:
            messagebox.showerror("Could Not Update Dead by Daylight", str(exc))

    def _run_legendary(
        self,
        arguments,
        activity,
        on_success=None,
        splash_profile=None,
        account=None,
        auth_client=False,
    ):
        if self.running or self.preset_running:
            messagebox.showinfo(
                "Operation in Progress",
                "Please wait for the current operation to finish.",
            )
            return
        try:
            if splash_profile:
                splash_file, backup_file = self.manager.prepare_eac_splash(
                    splash_profile
                )
                self._append_output(
                    f"EAC splash labelled for '{splash_profile}': "
                    f"{splash_file}\n"
                    f"Original EAC splash backup: {backup_file}\n"
                )
            command_factory = (
                self.manager.auth_command if auth_client else self.manager.command
            )
            command, env = command_factory(arguments, account=account)
        except ManagerError as exc:
            messagebox.showerror("Could Not Start Legendary", str(exc))
            return

        self.running = True
        self.on_command_success = on_success
        self.status_var.set(activity)
        self.progress.start(12)
        displayed_arguments = _redact_command_arguments(arguments)
        self._append_output(f"\n> legendary {' '.join(displayed_arguments)}\n")
        self._command_thread = threading.Thread(
            target=self._command_worker,
            args=(command, env),
            daemon=True,
        )
        self._command_thread.start()

    def _command_worker(self, command, env):
        try:
            result = self.command_runner.stream(
                command,
                env,
                lambda line: self.output_queue.put(("text", line)),
            )
            self.output_queue.put(("done", result.return_code))
        except OSError as exc:
            self.output_queue.put(("error", str(exc)))

    def _drain_output_queue(self):
        try:
            while True:
                event, value = self.output_queue.get_nowait()
                if event == "text":
                    self._append_output(value)
                elif event == "done":
                    self._append_output(f"Command finished (code {value}).\n")
                    callback = self.on_command_success if value == 0 else None
                    self._finish_command()
                    if callback:
                        callback()
                elif event == "error":
                    self._append_output(f"Error: {value}\n")
                    self._finish_command()
                    if not self._closing:
                        messagebox.showerror("Execution Error", value)
                elif event == "preset_text":
                    self._append_output(value)
                elif event == "preset_status":
                    self.status_var.set(value)
                elif event == "preset_done":
                    self._append_output(f"Preset '{value}' finished launching.\n")
                    self._finish_preset()
                elif event == "preset_error":
                    self._append_output(f"Preset error: {value}\n")
                    self._finish_preset()
                    if not self._closing:
                        messagebox.showerror("Preset Launch Error", value)
        except queue.Empty:
            pass
        if not self._closing:
            self.after(100, self._drain_output_queue)

    def _finish_command(self):
        self.running = False
        self.on_command_success = None
        self.progress.stop()
        self._set_status()

    def _finish_preset(self):
        self.preset_running = False
        self.progress.stop()
        self._set_status()

    def _request_close(self):
        workers = (self._command_thread, self._preset_thread)
        active = any(worker and worker.is_alive() for worker in workers)
        if active and not messagebox.askyesno(
            "Exit Better Together",
            "An operation is still running. Cancel it and exit?",
            parent=self,
        ):
            return
        self._closing = True
        self._preset_cancel_event.set()
        self.command_runner.terminate_streaming()
        self.status_var.set("Closing safely…")
        self._close_deadline = time.monotonic() + 3
        self.after(25, self._finish_close)

    def _finish_close(self):
        workers = (self._command_thread, self._preset_thread)
        active = any(worker and worker.is_alive() for worker in workers)
        if active and time.monotonic() < self._close_deadline:
            self.after(50, self._finish_close)
            return
        self.destroy()

    def _append_output(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")
