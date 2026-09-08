"""Shared visual theme and custom Tk widgets."""

import ctypes
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

DEFAULT_ACCENT = "#CF4C5C"

DARK_COLORS = {
    "bg": "#0C1017",
    "surface": "#141A24",
    "surface_alt": "#1C2430",
    "surface_hover": "#273242",
    "input": "#101620",
    "border": "#2B3545",
    "border_focus": "#CF4C5C",
    "text": "#F2F5F8",
    "muted": "#97A2B2",
    "subtle": "#667183",
    "success": "#55C889",
    "warning": "#E8B45B",
    "danger": "#D85B68",
    "danger_hover": "#EA6B78",
    "danger_border": "#5B3038",
    "danger_surface": "#35232A",
    "danger_pressed": "#41252B",
    "console": "#090C11",
    "console_text": "#C5CEDA",
    "shadow": "#070A0F",
}

LIGHT_COLORS = {
    "bg": "#F5F7FB",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF2F7",
    "surface_hover": "#E1E7EF",
    "input": "#F9FBFD",
    "border": "#D7DFE9",
    "text": "#171B23",
    "muted": "#596575",
    "subtle": "#8792A2",
    "success": "#168352",
    "warning": "#A86A0B",
    "danger": "#C83F50",
    "danger_hover": "#A92F3F",
    "danger_border": "#E5A8B0",
    "danger_surface": "#FCECEF",
    "danger_pressed": "#F5D8DD",
    "console": "#F7F9FC",
    "console_text": "#303947",
    "shadow": "#DCE3EC",
}

# This dictionary is intentionally mutated in place so modules that import
# COLORS always see the current palette.
COLORS = dict(DARK_COLORS)

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BODY = ("Segoe UI", 10)
FONT_MEDIUM = ("Segoe UI Semibold", 10)
FONT_SECTION = ("Segoe UI Semibold", 11)
FONT_TITLE = ("Segoe UI Semibold", 23)


def normalize_accent(value):
    value = str(value or "").strip().upper()
    return value if re.fullmatch(r"#[0-9A-F]{6}", value) else DEFAULT_ACCENT


def _blend(color, target, amount):
    color_rgb = tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
    target_rgb = tuple(int(target[index : index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(
        round(source + (destination - source) * amount)
        for source, destination in zip(color_rgb, target_rgb, strict=False)
    )
    return "#" + "".join(f"{channel:02X}" for channel in mixed)


def _contrast_text(color):
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return "#11151B" if luminance > 0.42 else "#FFFFFF"


def configure_theme(root, mode="dark", accent=DEFAULT_ACCENT):
    """Apply the shared Better Together visual system to a Tk application."""
    mode = "light" if mode == "light" else "dark"
    accent = normalize_accent(accent)
    palette = dict(LIGHT_COLORS if mode == "light" else DARK_COLORS)
    palette.update(
        {
            "accent": accent,
            "accent_hover": _blend(
                accent,
                "#000000" if mode == "light" else "#FFFFFF",
                0.13,
            ),
            "accent_pressed": _blend(accent, "#000000", 0.22),
            "accent_text": _contrast_text(accent),
            "border_focus": accent,
        }
    )
    COLORS.clear()
    COLORS.update(palette)

    root.configure(background=COLORS["bg"])
    root.option_add("*Font", FONT)
    root.option_add("*Menu.background", COLORS["surface"])
    root.option_add("*Menu.foreground", COLORS["text"])
    root.option_add("*Menu.activeBackground", COLORS["accent"])
    root.option_add("*Menu.activeForeground", COLORS["accent_text"])

    style = ttk.Style(root)
    style.theme_use("clam")

    # Tk's default class bindings change closed combobox and spinbox values
    # when the pointer is merely hovering over them. Remove those bindings so
    # the wheel can keep scrolling an enclosing settings view instead.
    for widget_class in ("TCombobox", "TSpinbox"):
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.unbind_class(widget_class, sequence)

    style.configure(
        ".",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=FONT,
    )
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("App.TFrame", background=COLORS["bg"])
    style.configure(
        "Card.TFrame",
        background=COLORS["surface"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        relief="solid",
    )
    style.configure("CardInner.TFrame", background=COLORS["surface"])
    style.configure("Inset.TFrame", background=COLORS["surface_alt"])
    style.configure("Status.TFrame", background=COLORS["surface_alt"])

    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure(
        "Title.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=FONT_TITLE,
    )
    style.configure(
        "Eyebrow.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["accent"],
        font=("Segoe UI Semibold", 9),
    )
    style.configure(
        "Subtitle.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["muted"],
        font=FONT_BODY,
    )
    style.configure(
        "CardTitle.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 12),
    )
    style.configure(
        "CardText.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=FONT_BODY,
    )
    style.configure(
        "CardMuted.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["muted"],
        font=FONT_SMALL,
    )
    style.configure(
        "FieldLabel.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["muted"],
        font=FONT_SMALL,
    )
    style.configure(
        "Status.TLabel",
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        font=FONT_SMALL,
        padding=(10, 5),
    )
    style.configure(
        "Badge.TLabel",
        background=COLORS["surface_alt"],
        foreground=COLORS["muted"],
        font=("Segoe UI Semibold", 8),
        padding=(8, 4),
    )
    style.configure(
        "AccentBadge.TLabel",
        background=COLORS["accent"],
        foreground=COLORS["accent_text"],
        font=("Segoe UI Semibold", 8),
        padding=(8, 4),
    )

    style.configure(
        "TButton",
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        focusthickness=1,
        focuscolor=COLORS["border_focus"],
        padding=(12, 8),
        relief="flat",
        font=FONT_MEDIUM,
    )
    style.map(
        "TButton",
        background=[
            ("disabled", COLORS["surface"]),
            ("pressed", COLORS["input"]),
            ("active", COLORS["surface_hover"]),
        ],
        foreground=[("disabled", COLORS["subtle"])],
        bordercolor=[("active", COLORS["border_focus"])],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground=COLORS["accent_text"],
        bordercolor=COLORS["accent"],
        padding=(15, 9),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", COLORS["surface_alt"]),
            ("pressed", COLORS["accent_pressed"]),
            ("active", COLORS["accent_hover"]),
        ],
        foreground=[("disabled", COLORS["subtle"])],
        bordercolor=[
            ("pressed", COLORS["accent_pressed"]),
            ("active", COLORS["accent_hover"]),
        ],
    )
    style.configure(
        "Launch.TButton",
        background=COLORS["accent"],
        foreground=COLORS["accent_text"],
        bordercolor=COLORS["accent"],
        padding=(18, 13),
        font=("Segoe UI Semibold", 11),
    )
    style.map(
        "Launch.TButton",
        background=[
            ("pressed", COLORS["accent_pressed"]),
            ("active", COLORS["accent_hover"]),
        ],
        bordercolor=[("active", COLORS["accent_hover"])],
    )
    style.configure(
        "Danger.TButton",
        background=COLORS["surface_alt"],
        foreground=COLORS["danger"],
        bordercolor=COLORS["danger_border"],
    )
    style.map(
        "Danger.TButton",
        background=[
            ("pressed", COLORS["danger_pressed"]),
            ("active", COLORS["danger_surface"]),
        ],
        foreground=[("active", COLORS["danger_hover"])],
        bordercolor=[("active", COLORS["danger_hover"])],
    )
    style.configure("Compact.TButton", padding=(10, 6), font=FONT_SMALL)
    style.configure(
        "AccentCompact.TButton",
        background=COLORS["accent"],
        foreground=COLORS["accent_text"],
        bordercolor=COLORS["accent"],
        borderwidth=1,
        padding=(10, 6),
        relief="flat",
        font=FONT_SMALL,
    )
    style.map(
        "AccentCompact.TButton",
        background=[
            ("pressed", COLORS["accent_pressed"]),
            ("active", COLORS["accent_hover"]),
        ],
        bordercolor=[("active", COLORS["accent_hover"])],
    )

    field_settings = {
        "fieldbackground": COLORS["input"],
        "background": COLORS["input"],
        "foreground": COLORS["text"],
        "insertcolor": COLORS["text"],
        "bordercolor": COLORS["border"],
        "lightcolor": COLORS["border"],
        "darkcolor": COLORS["border"],
        "padding": 9,
        "relief": "flat",
    }
    style.configure("TEntry", **field_settings)
    style.map(
        "TEntry",
        bordercolor=[("focus", COLORS["border_focus"])],
        fieldbackground=[("readonly", COLORS["input"])],
        foreground=[("readonly", COLORS["muted"])],
    )
    style.configure(
        "TCombobox",
        **field_settings,
        arrowsize=24,
        arrowcolor=COLORS["muted"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", COLORS["input"]),
            ("focus", COLORS["input"]),
        ],
        foreground=[("readonly", COLORS["text"])],
        selectbackground=[("readonly", COLORS["input"])],
        selectforeground=[("readonly", COLORS["text"])],
        bordercolor=[("focus", COLORS["border_focus"])],
        arrowcolor=[("active", COLORS["text"])],
    )
    style.configure("TSpinbox", **field_settings, arrowcolor=COLORS["muted"])
    style.map("TSpinbox", bordercolor=[("focus", COLORS["border_focus"])])

    style.configure(
        "TCheckbutton",
        background=COLORS["bg"],
        foreground=COLORS["muted"],
        indicatorbackground=COLORS["input"],
        indicatorforeground=COLORS["accent_text"],
        indicatorcolor=COLORS["input"],
        bordercolor=COLORS["border"],
        focuscolor=COLORS["border_focus"],
        padding=4,
    )
    style.map(
        "TCheckbutton",
        background=[("active", COLORS["bg"])],
        foreground=[("active", COLORS["text"])],
        indicatorbackground=[("selected", COLORS["accent"])],
        indicatorcolor=[("selected", COLORS["accent"])],
    )
    style.configure("Card.TCheckbutton", background=COLORS["surface"])
    style.map("Card.TCheckbutton", background=[("active", COLORS["surface"])])

    style.configure(
        "TProgressbar",
        background=COLORS["accent"],
        troughcolor=COLORS["surface_alt"],
        bordercolor=COLORS["surface_alt"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        thickness=6,
    )
    style.configure(
        "TScale",
        background=COLORS["accent"],
        troughcolor=COLORS["surface_alt"],
        bordercolor=COLORS["surface_alt"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        sliderlength=18,
    )
    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["surface_alt"],
        troughcolor=COLORS["console"],
        bordercolor=COLORS["console"],
        arrowcolor=COLORS["muted"],
        relief="flat",
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", COLORS["surface_hover"])],
    )

    style.configure(
        "TNotebook",
        background=COLORS["bg"],
        bordercolor=COLORS["border"],
        borderwidth=0,
        tabmargins=(0, 0, 0, 10),
    )
    style.configure(
        "TNotebook.Tab",
        background=COLORS["surface_alt"],
        foreground=COLORS["muted"],
        padding=(18, 10),
        borderwidth=0,
        font=FONT_MEDIUM,
    )
    style.map(
        "TNotebook.Tab",
        background=[
            ("selected", COLORS["accent"]),
            ("active", COLORS["surface_hover"]),
        ],
        foreground=[
            ("selected", COLORS["accent_text"]),
            ("active", COLORS["text"]),
        ],
    )

    style.configure(
        "TLabelframe",
        background=COLORS["bg"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "TLabelframe.Label",
        background=COLORS["bg"],
        foreground=COLORS["muted"],
        font=FONT_MEDIUM,
    )
    style.configure("TSeparator", background=COLORS["border"])
    return style


def _mix(first, second, amount):
    first_rgb = tuple(int(first[index : index + 2], 16) for index in (1, 3, 5))
    second_rgb = tuple(int(second[index : index + 2], 16) for index in (1, 3, 5))
    result = tuple(
        round(start + (end - start) * amount)
        for start, end in zip(first_rgb, second_rgb, strict=False)
    )
    return "#" + "".join(f"{channel:02X}" for channel in result)


def _widget_background(widget):
    try:
        background = widget.cget("background")
        if isinstance(background, str) and background:
            return background
    except (AttributeError, tk.TclError):
        pass
    try:
        style_name = widget.cget("style") or widget.winfo_class()
        background = ttk.Style(widget).lookup(style_name, "background")
        if background:
            return background
    except (AttributeError, tk.TclError):
        pass
    return COLORS["bg"]


def _rounded_polygon(canvas, x1, y1, x2, y2, radius, **options):
    radius = max(1, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = (
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    )
    return canvas.create_polygon(
        points,
        smooth=True,
        splinesteps=32,
        **options,
    )


class SmoothCard(tk.Frame):
    """A rounded, softly elevated container with a regular child frame."""

    def __init__(
        self,
        parent,
        *,
        padding=18,
        radius=18,
        fill_key="surface",
        shadow=True,
    ):
        self.padding = self._normalize_padding(padding)
        self.radius = radius
        self.fill_key = fill_key
        self.shadow = shadow
        self._outside = _widget_background(parent)
        super().__init__(
            parent,
            background=self._outside,
            borderwidth=0,
            highlightthickness=0,
            width=160,
            height=100,
        )
        self.canvas = tk.Canvas(
            self,
            background=self._outside,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(
            self,
            background=COLORS[self.fill_key],
            borderwidth=0,
            highlightthickness=0,
        )
        self.body.place(
            x=self.padding[0],
            y=self.padding[1],
            relwidth=1,
            relheight=1,
            width=-(self.padding[0] + self.padding[2]),
            height=-(self.padding[1] + self.padding[3] + (3 if shadow else 0)),
        )
        self.bind("<Configure>", self._redraw, add="+")
        self.body.bind("<Configure>", self._sync_requested_size, add="+")
        self.after_idle(self._sync_requested_size)

    @staticmethod
    def _normalize_padding(padding):
        if isinstance(padding, (tuple, list)):
            if len(padding) == 2:
                return (padding[0], padding[1], padding[0], padding[1])
            if len(padding) == 4:
                return tuple(padding)
        return (padding, padding, padding, padding)

    def _sync_requested_size(self, _event=None):
        if not self.winfo_exists():
            return
        left, top, right, bottom = self.padding
        requested_width = max(80, self.body.winfo_reqwidth() + left + right)
        requested_height = max(
            48,
            self.body.winfo_reqheight() + top + bottom + (3 if self.shadow else 0),
        )
        tk.Frame.configure(
            self,
            width=requested_width,
            height=requested_height,
        )

    def _redraw(self, _event=None):
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 4 or height < 4:
            return
        self.canvas.delete("surface")
        if self.shadow:
            _rounded_polygon(
                self.canvas,
                2,
                4,
                width - 2,
                height - 1,
                self.radius,
                fill=COLORS["shadow"],
                outline="",
                tags="surface",
            )
        _rounded_polygon(
            self.canvas,
            1,
            1,
            width - 2,
            height - (4 if self.shadow else 2),
            self.radius,
            fill=COLORS[self.fill_key],
            outline=COLORS["border"],
            width=1,
            tags="surface",
        )
        self.canvas.tag_lower("surface")

    def refresh_theme(self):
        self._outside = _widget_background(self.master)
        self.configure(background=self._outside)
        self.canvas.configure(background=self._outside)
        self.body.configure(background=COLORS[self.fill_key])
        self._redraw()


class SmoothButton(tk.Canvas):
    """Canvas-backed rounded button with short hover/press transitions."""

    _STYLE_SPECS = {
        "TButton": (40, 12, 13, FONT_MEDIUM),
        "Accent.TButton": (42, 13, 15, FONT_MEDIUM),
        "Launch.TButton": (50, 15, 18, ("Segoe UI Semibold", 11)),
        "Danger.TButton": (40, 12, 13, FONT_MEDIUM),
        "Compact.TButton": (34, 10, 11, FONT_SMALL),
        "AccentCompact.TButton": (34, 10, 11, FONT_SMALL),
    }

    def __init__(
        self,
        parent,
        *,
        text="",
        textvariable=None,
        command=None,
        style="TButton",
        state="normal",
        width=None,
        **_kwargs,
    ):
        self.button_style = style or "TButton"
        height, self.radius, self.pad_x, self.button_font = self._STYLE_SPECS.get(
            self.button_style,
            self._STYLE_SPECS["TButton"],
        )
        self.command = command
        self.button_state = state
        self.textvariable = textvariable
        self._text = str(text)
        self._hovered = False
        self._pressed = False
        self._animation = None
        self._outside = _widget_background(parent)
        font = tkfont.Font(font=self.button_font)
        requested_width = width or max(
            72, font.measure(self._display_text()) + self.pad_x * 2
        )
        super().__init__(
            parent,
            width=requested_width,
            height=height,
            background=self._outside,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            cursor="hand2" if state != "disabled" else "arrow",
            takefocus=1,
        )
        self._current_fill = self._colors()[0]
        self.bind("<Configure>", self._redraw, add="+")
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")
        self.bind("<ButtonPress-1>", self._press, add="+")
        self.bind("<ButtonRelease-1>", self._release, add="+")
        self.bind("<FocusIn>", self._redraw, add="+")
        self.bind("<FocusOut>", self._redraw, add="+")
        self.bind("<space>", self._keyboard_invoke, add="+")
        self.bind("<Return>", self._keyboard_invoke, add="+")
        if textvariable is not None:
            self._trace_id = textvariable.trace_add("write", self._variable_changed)
        else:
            self._trace_id = None
        self.after_idle(self._redraw)

    def _display_text(self):
        if self.textvariable is not None:
            return str(self.textvariable.get())
        return self._text

    def _colors(self):
        if self.button_style in {
            "Accent.TButton",
            "Launch.TButton",
            "AccentCompact.TButton",
        }:
            return (
                COLORS["accent"],
                COLORS["accent_hover"],
                COLORS["accent_pressed"],
                COLORS["accent_text"],
                COLORS["accent"],
            )
        if self.button_style == "Danger.TButton":
            return (
                COLORS["surface_alt"],
                COLORS["danger_surface"],
                COLORS["danger_pressed"],
                COLORS["danger"],
                COLORS["danger_border"],
            )
        return (
            COLORS["surface_alt"],
            COLORS["surface_hover"],
            COLORS["input"],
            COLORS["text"],
            COLORS["border"],
        )

    def _target_fill(self):
        normal, hover, pressed, _text, _outline = self._colors()
        if self.button_state == "disabled":
            return COLORS["surface_alt"]
        if self._pressed:
            return pressed
        if self._hovered:
            return hover
        return normal

    def _animate_to_state(self):
        if self._animation is not None:
            self.after_cancel(self._animation)
        target = self._target_fill()

        def step(remaining):
            self._current_fill = _mix(
                self._current_fill,
                target,
                0.48 if remaining > 1 else 1.0,
            )
            self._redraw()
            if remaining > 1 and self.winfo_exists():
                self._animation = self.after(16, lambda: step(remaining - 1))
            else:
                self._animation = None

        step(5)

    def _redraw(self, _event=None):
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 4 or height < 4:
            return
        self.delete("all")
        _normal, _hover, _pressed, text_color, outline = self._colors()
        if self.button_state == "disabled":
            text_color = COLORS["subtle"]
            outline = COLORS["border"]
        if self.focus_get() is self and self.button_state != "disabled":
            outline = COLORS["border_focus"]
        _rounded_polygon(
            self,
            1,
            1,
            width - 2,
            height - 2,
            self.radius,
            fill=self._current_fill,
            outline=outline,
            width=1,
        )
        self.create_text(
            width / 2,
            height / 2,
            text=self._display_text(),
            fill=text_color,
            font=self.button_font,
        )

    def _enter(self, _event=None):
        if self.button_state == "disabled":
            return
        self._hovered = True
        self._animate_to_state()

    def _leave(self, _event=None):
        self._hovered = False
        self._pressed = False
        self._animate_to_state()

    def _press(self, _event=None):
        if self.button_state == "disabled":
            return
        self.focus_set()
        self._pressed = True
        self._animate_to_state()

    def _release(self, event):
        if self.button_state == "disabled":
            return
        inside = (
            0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        )
        was_pressed = self._pressed
        self._pressed = False
        self._hovered = inside
        self._animate_to_state()
        if was_pressed and inside and callable(self.command):
            self.command()

    def _keyboard_invoke(self, _event=None):
        if self.button_state != "disabled" and callable(self.command):
            self.command()
        return "break"

    def _variable_changed(self, *_args):
        self._redraw()

    def configure(self, cnf=None, **kwargs):
        options = {}
        if isinstance(cnf, dict):
            options.update(cnf)
        options.update(kwargs)
        if "text" in options:
            self._text = str(options.pop("text"))
        if "textvariable" in options:
            options.pop("textvariable")
        if "command" in options:
            self.command = options.pop("command")
        if "state" in options:
            self.button_state = options.pop("state")
            self.configure(
                cursor="hand2" if self.button_state != "disabled" else "arrow"
            )
        result = tk.Canvas.configure(self, **options) if options else None
        if self.winfo_exists():
            self._current_fill = self._target_fill()
            self._redraw()
        return result

    config = configure

    def cget(self, key):
        if key == "text":
            return self._display_text()
        if key == "state":
            return self.button_state
        if key == "style":
            return self.button_style
        return tk.Canvas.cget(self, key)

    def invoke(self):
        if self.button_state != "disabled" and callable(self.command):
            return self.command()
        return None

    def refresh_theme(self):
        self._outside = _widget_background(self.master)
        tk.Canvas.configure(self, background=self._outside)
        self._current_fill = self._target_fill()
        self._redraw()


def refresh_smooth_widgets(root):
    widgets = [root]
    for widget in widgets:
        try:
            widgets.extend(widget.winfo_children())
        except tk.TclError:
            continue
        refresh = getattr(widget, "refresh_theme", None)
        if callable(refresh):
            refresh()


def install_smooth_button_adapter():
    """Use SmoothButton anywhere this application constructs ttk.Button."""
    ttk.Button = SmoothButton


def enable_window_rounding(window, dark=False):
    """Ask Windows 11 for rounded outer corners and a matching title bar."""
    if sys.platform != "win32":
        return

    def apply():
        try:
            hwnd = window.winfo_id()
            preference = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                33,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
            dark_value = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                20,
                ctypes.byref(dark_value),
                ctypes.sizeof(dark_value),
            )
        except (AttributeError, OSError, tk.TclError):
            pass

    window.after_idle(apply)
