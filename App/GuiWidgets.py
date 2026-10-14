import json
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

import HelpText

# Flat theme drawn natively by Tk's clam engine: much faster to draw than image-based themes.
PALETTES = {
    "dark": {
        "background": "#1e1f22", "surface": "#2b2d31", "surfaceAlt": "#383a40", "hover": "#43464d", "border": "#4a4d55",
        "foreground": "#dcdee3", "strong": "#ffffff", "muted": "#9da3ad",
        "accent": "#3d8bfd", "accentHover": "#5c9dff", "accentText": "#ffffff", "selection": "#2c4a75",
        "heading": "#7db8ff", "code": "#1c2e42", "codeText": "#a6d1ff",
        "canvas": "#141518", "canvasText": "#b4b9c2",
        "failed": "#ff6b6b", "warning": "#ffc145", "success": "#4ccb73",
        "chipBorder": "#6a6e78", "chipEmpty": "#2b2d31",
    },
    "light": {
        "background": "#f3f4f6", "surface": "#ffffff", "surfaceAlt": "#e8eaee", "hover": "#dcdfe5", "border": "#c5cad3",
        "foreground": "#24292f", "strong": "#000000", "muted": "#59606b",
        "accent": "#0a64d8", "accentHover": "#0b55b5", "accentText": "#ffffff", "selection": "#cfe2ff",
        "heading": "#0a58c2", "code": "#e3eefb", "codeText": "#0b4f8a",
        "canvas": "#d5d8dd", "canvasText": "#3a3f47",
        "failed": "#c4281c", "warning": "#a35800", "success": "#1a7f37",
        "chipBorder": "#8a9099", "chipEmpty": "#e8eaee",
    },
}

# Status kinds -> label styles. Colour only ever marks one of these states.
STATUS_STYLES = {"": "TLabel", "failed": "Failed.TLabel", "warning": "Warning.TLabel", "success": "Success.TLabel", "muted": "Muted.TLabel"}

THEME_NAME = "imagecolour"


class Settings:
    """Small per-user preferences, stored next to the app. Missing or damaged files fall back to defaults."""

    DEFAULTS = {"theme": "dark", "showWelcome": True, "fineTuning": False, "autoRender": False, "fullResolution": False}

    def __init__(self, path):
        self.path = Path(path)
        self.values = dict(self.DEFAULTS)
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            self.values.update({key: value for key, value in stored.items() if key in self.DEFAULTS})
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value
        try:
            self.path.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
        except OSError:
            pass


def pickFamily(candidates):
    available = set(tkfont.families())
    return next((family for family in candidates if family in available), "TkDefaultFont")


class Theme:
    """The app's own flat theme in a dark and a light variant. Widgets with their own colours register onChange."""

    def __init__(self, root):
        self.root = root
        self.mode = None
        self.palette = None
        self.listeners = []
        self.windows = [root]
        self.style = ttk.Style(root)

        if sys.platform.startswith("win"):
            body = pickFamily(["Segoe UI Variable Text", "Segoe UI"])
            display = pickFamily(["Segoe UI Variable Display", "Segoe UI"])
            mono = pickFamily(["Cascadia Mono", "Consolas"])
        elif sys.platform == "darwin":
            body = display = pickFamily(["SF Pro Text", "Helvetica Neue", "Helvetica"])
            mono = pickFamily(["SF Mono", "Menlo"])
        else:
            body = display = pickFamily(["Inter", "Noto Sans", "Ubuntu", "DejaVu Sans"])
            mono = pickFamily(["DejaVu Sans Mono", "Liberation Mono"])
        self.fonts = {
            "AppBody": tkfont.Font(root, name="AppBody", family=body, size=10),
            "AppStrong": tkfont.Font(root, name="AppStrong", family=body, size=10, weight="bold"),
            "AppItalic": tkfont.Font(root, name="AppItalic", family=body, size=10, slant="italic"),
            "AppSmall": tkfont.Font(root, name="AppSmall", family=body, size=9),
            "AppHeading": tkfont.Font(root, name="AppHeading", family=body, size=11, weight="bold"),
            "AppSubtitle": tkfont.Font(root, name="AppSubtitle", family=display, size=14, weight="bold"),
            "AppTitle": tkfont.Font(root, name="AppTitle", family=display, size=20, weight="bold"),
            "AppMono": tkfont.Font(root, name="AppMono", family=mono, size=10),
        }

        if THEME_NAME not in self.style.theme_names():
            self.style.theme_create(THEME_NAME, parent="clam")
        self.style.theme_use(THEME_NAME)
        self.createSwitchElement()

    def createSwitchElement(self):
        scale = float(self.root.tk.call("tk", "scaling")) / (96 / 72)
        self.switchSize = (max(30, round(38 * scale)), max(16, round(20 * scale)))
        self.switchGap = round(8 * scale)
        blank = Image.new("RGBA", (self.switchSize[0] + self.switchGap, self.switchSize[1]))
        self.switchImages = {"off": ImageTk.PhotoImage(blank), "on": ImageTk.PhotoImage(blank)}
        self.style.element_create("Switch.indicator", "image", self.switchImages["off"], ("selected", self.switchImages["on"]), sticky="w")
        self.style.layout("Switch.TCheckbutton", [
            ("Checkbutton.padding", {"sticky": "nswe", "children": [
                ("Switch.indicator", {"side": "left", "sticky": ""}),
                ("Checkbutton.label", {"side": "left", "sticky": "w"}),
            ]}),
        ])

    def drawSwitch(self, on):
        palette = self.palette
        width, height = self.switchSize
        factor = 4
        image = Image.new("RGBA", (width * factor, height * factor), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        box = (0, 0, width * factor - 1, height * factor - 1)
        radius = height * factor // 2
        if on:
            draw.rounded_rectangle(box, radius, fill=palette["accent"])
            knobColour = palette["accentText"]
        else:
            draw.rounded_rectangle(box, radius, fill=palette["surface"], outline=palette["muted"], width=factor * 2)
            knobColour = palette["muted"]
        inset = factor * 4
        knob = height * factor - 2 * inset
        left = width * factor - inset - knob if on else inset
        draw.ellipse((left, inset, left + knob, inset + knob), fill=knobColour)
        # Transparent space after the switch separates it from its label
        withGap = Image.new("RGBA", (width + self.switchGap, height), (0, 0, 0, 0))
        withGap.paste(image.resize((width, height), Image.Resampling.LANCZOS), (0, 0))
        return withGap

    def apply(self, mode):
        self.mode = mode
        self.palette = p = PALETTES[mode]
        style = self.style

        style.configure(".", background=p["background"], foreground=p["foreground"], fieldbackground=p["surface"],
                        bordercolor=p["border"], lightcolor=p["background"], darkcolor=p["background"], troughcolor=p["surface"],
                        selectbackground=p["selection"], selectforeground=p["strong"], insertcolor=p["strong"],
                        focuscolor=p["accent"], arrowcolor=p["foreground"], font="AppBody", relief="flat")
        style.map(".", foreground=[("disabled", p["muted"])])

        style.configure("TFrame", background=p["background"])
        style.configure("Card.TFrame", background=p["surface"])
        style.configure("Tooltip.TFrame", background=p["surfaceAlt"], bordercolor=p["border"], relief="solid", borderwidth=1)

        style.configure("TLabel", background=p["background"], foreground=p["foreground"])
        for kind in ("failed", "warning", "success", "muted"):
            style.configure(STATUS_STYLES[kind], foreground=p[kind])
        style.configure("Title.TLabel", font="AppTitle", foreground=p["strong"])
        style.configure("Subtitle.TLabel", font="AppSubtitle", foreground=p["strong"])
        style.configure("Strong.TLabel", font="AppStrong", foreground=p["strong"])
        style.configure("Heading.TLabel", font="AppHeading", foreground=p["strong"])
        style.configure("Card.TLabel", background=p["surface"], foreground=p["foreground"])
        style.configure("Step.TLabel", background=p["surface"], foreground=p["heading"], font="AppStrong")
        style.configure("Tooltip.TLabel", background=p["surfaceAlt"], foreground=p["foreground"])
        style.configure("Tab.TLabel", font="AppHeading", foreground=p["muted"], padding=(14, 8))
        style.configure("TabSelected.TLabel", font="AppHeading", foreground=p["strong"], padding=(14, 8))

        buttonPadding = (14, 6)
        style.configure("TButton", background=p["surfaceAlt"], foreground=p["foreground"], bordercolor=p["border"],
                        lightcolor=p["surfaceAlt"], darkcolor=p["surfaceAlt"], padding=buttonPadding, anchor="center", focusthickness=0)
        style.map("TButton", background=[("disabled", p["surface"]), ("pressed", p["border"]), ("active", p["hover"])],
                  lightcolor=[("disabled", p["surface"]), ("pressed", p["border"]), ("active", p["hover"])],
                  darkcolor=[("disabled", p["surface"]), ("pressed", p["border"]), ("active", p["hover"])],
                  bordercolor=[("disabled", p["surfaceAlt"]), ("focus", p["accent"])], foreground=[("disabled", p["muted"])])
        style.configure("Accent.TButton", background=p["accent"], foreground=p["accentText"], bordercolor=p["accent"],
                        lightcolor=p["accent"], darkcolor=p["accent"], font="AppStrong")
        style.map("Accent.TButton", background=[("disabled", p["surfaceAlt"]), ("pressed", p["accentHover"]), ("active", p["accentHover"])],
                  lightcolor=[("disabled", p["surfaceAlt"]), ("active", p["accentHover"])], darkcolor=[("disabled", p["surfaceAlt"]), ("active", p["accentHover"])],
                  bordercolor=[("disabled", p["surfaceAlt"]), ("active", p["accentHover"])], foreground=[("disabled", p["muted"])])
        style.configure("Help.TButton", padding=(8, 2), font="AppStrong", foreground=p["heading"])

        style.configure("Toggle.Toolbutton", background=p["surfaceAlt"], foreground=p["foreground"], bordercolor=p["border"],
                        lightcolor=p["surfaceAlt"], darkcolor=p["surfaceAlt"], padding=(12, 5), anchor="center")
        style.map("Toggle.Toolbutton", background=[("selected", p["accent"]), ("active", p["hover"])],
                  foreground=[("selected", p["accentText"])], lightcolor=[("selected", p["accent"])], darkcolor=[("selected", p["accent"])],
                  bordercolor=[("selected", p["accent"])])

        for widget in ("TEntry", "TCombobox", "TSpinbox"):
            style.configure(widget, fieldbackground=p["surface"], foreground=p["strong"], bordercolor=p["border"],
                            lightcolor=p["surface"], darkcolor=p["surface"], arrowcolor=p["foreground"], padding=(8, 5),
                            insertcolor=p["strong"], selectbackground=p["selection"], selectforeground=p["strong"])
            style.map(widget, bordercolor=[("focus", p["accent"]), ("hover", p["muted"])],
                      fieldbackground=[("disabled", p["background"]), ("readonly", p["surface"])],
                      foreground=[("disabled", p["muted"])], arrowcolor=[("disabled", p["muted"])],
                      lightcolor=[("focus", p["surface"])], darkcolor=[("focus", p["surface"])],
                      selectbackground=[("readonly", "!focus", p["surface"]), ("readonly", "focus", p["selection"])],
                      selectforeground=[("readonly", p["strong"])])
        for widget in ("TCombobox", "TSpinbox"):
            # clam maps the arrow buttons to its own light grey, e.g. for read-only comboboxes
            style.configure(widget, background=p["surfaceAlt"])
            style.map(widget, background=[("disabled", p["background"]), ("pressed", p["border"]), ("active", p["hover"]),
                                          ("readonly", p["surfaceAlt"]), ("!disabled", p["surfaceAlt"])])

        style.configure("TCheckbutton", background=p["background"], foreground=p["foreground"], indicatorbackground=p["surface"],
                        indicatorforeground=p["accent"], padding=(2, 4))
        style.map("TCheckbutton", background=[("active", p["background"])])
        style.configure("Switch.TCheckbutton", padding=(0, 4))

        style.configure("Treeview", background=p["surface"], fieldbackground=p["surface"], foreground=p["foreground"],
                        bordercolor=p["border"], lightcolor=p["surface"], darkcolor=p["surface"], rowheight=30)
        style.map("Treeview", background=[("selected", p["selection"])], foreground=[("selected", p["strong"])])
        style.configure("Treeview.Heading", background=p["surfaceAlt"], foreground=p["strong"], bordercolor=p["border"],
                        lightcolor=p["surfaceAlt"], darkcolor=p["surfaceAlt"], font="AppStrong", padding=(8, 5), relief="flat")
        style.map("Treeview.Heading", background=[("active", p["hover"])])

        style.configure("TLabelframe", background=p["background"], bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"],
                        relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=p["background"], foreground=p["strong"], font="AppHeading")
        style.configure("TPanedwindow", background=p["background"])
        style.configure("Sash", sashthickness=8, gripcount=0, background=p["background"], lightcolor=p["background"], bordercolor=p["background"])
        style.configure("TScrollbar", background=p["surfaceAlt"], troughcolor=p["background"], bordercolor=p["background"],
                        lightcolor=p["surfaceAlt"], darkcolor=p["surfaceAlt"], arrowcolor=p["muted"], gripcount=0)
        style.map("TScrollbar", background=[("active", p["hover"])])
        style.configure("TProgressbar", background=p["accent"], troughcolor=p["surface"], bordercolor=p["border"],
                        lightcolor=p["accent"], darkcolor=p["accent"])
        style.configure("TSeparator", background=p["border"])

        for state, image in self.switchImages.items():
            image.paste(self.drawSwitch(state == "on"))

        # Plain Tk widgets read these when they are created; existing ones are updated below
        for pattern, value in (("*TCombobox*Listbox.background", p["surface"]), ("*TCombobox*Listbox.foreground", p["strong"]),
                               ("*TCombobox*Listbox.selectBackground", p["selection"]), ("*TCombobox*Listbox.selectForeground", p["strong"]),
                               ("*TCombobox*Listbox.font", "AppBody")):
            self.root.option_add(pattern, value)
        self.updateComboboxLists(self.root)

        for listener in self.listeners:
            listener(p)
        for window in list(self.windows):
            self.decorate(window)

    def updateComboboxLists(self, widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Combobox):
                popdown = child.tk.call("ttk::combobox::PopdownWindow", child)
                child.tk.call(f"{popdown}.f.l", "configure", "-background", self.palette["surface"], "-foreground", self.palette["strong"],
                              "-selectbackground", self.palette["selection"], "-selectforeground", self.palette["strong"])
            self.updateComboboxLists(child)

    def onChange(self, listener):
        self.listeners.append(listener)
        if self.palette:
            listener(self.palette)

    def track(self, window):
        """Gives a new window the theme's background and title bar, and keeps it updated."""
        self.windows.append(window)
        window.bind("<Destroy>", lambda e: self.windows.remove(window) if e.widget is window and window in self.windows else None, add="+")
        self.decorate(window)

    def decorate(self, window):
        try:
            window.configure(background=self.palette["background"])
        except tk.TclError:
            return
        setDarkTitleBar(window, self.mode == "dark")


def setDarkTitleBar(window, dark):
    """Windows 10/11 draw the title bar light unless asked; other systems follow their own setting."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        window.update_idletasks()
        handle = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, and its pre-20H1 number
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass


class TabBar(ttk.Frame):
    """Tabs that raise pages stacked in one place, which redraws much faster than ttk.Notebook."""

    def __init__(self, parent, theme, container):
        super().__init__(parent)
        self.theme = theme
        self.container = container
        self.tabs = {}
        self.pages = {}
        self.current = None
        self.listeners = []
        theme.onChange(self.onTheme)

    def add(self, page, text):
        tab = ttk.Frame(self, cursor="hand2")
        tab.pack(side="left", padx=(0, 4))
        label = ttk.Label(tab, text=text, style="Tab.TLabel", cursor="hand2")
        label.pack()
        underline = tk.Frame(tab, height=3, background=self.theme.palette["background"])
        underline.pack(fill="x")
        for widget in (tab, label):
            widget.bind("<Button-1>", lambda _e, p=page: self.select(p))
        self.tabs[page] = (label, underline)
        page.place(in_=self.container, x=0, y=0, relwidth=1, relheight=1)
        if self.current is None:
            self.select(page)
        else:
            page.lower()

    def select(self, page):
        self.current = page
        page.lift()
        self.onTheme(self.theme.palette)
        for listener in self.listeners:
            listener(page)

    def onTheme(self, palette):
        for page, (label, underline) in self.tabs.items():
            selected = page is self.current
            label.configure(style="TabSelected.TLabel" if selected else "Tab.TLabel")
            underline.configure(background=palette["accent"] if selected else palette["background"])


class Tooltip:
    """Shows `text` next to a widget while the pointer rests on it."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        self.pending = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, _event=None):
        self.hide()
        self.pending = self.widget.after(450, self.show)

    def show(self):
        self.pending = None
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        frame = ttk.Frame(self.window, style="Tooltip.TFrame", padding=(10, 6))
        frame.pack()
        ttk.Label(frame, text=self.text, wraplength=380, justify="left", style="Tooltip.TLabel").pack()

    def hide(self, _event=None):
        if self.pending:
            self.widget.after_cancel(self.pending)
            self.pending = None
        if self.window:
            self.window.destroy()
            self.window = None


class AutoScrollbar(ttk.Scrollbar):
    """A scrollbar that hides itself when everything fits."""

    def set(self, first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        super().set(first, last)


def helpButton(parent, app, topic):
    button = ttk.Button(parent, text="?", style="Help.TButton", command=lambda: app.showHelp(topic))
    Tooltip(button, f"Help: {HelpText.TOPIC_TITLES[topic]}")
    return button


class GuideBanner(ttk.Frame):
    """The 'what to do next' bar at the top of a tab."""

    def __init__(self, parent, app, topic):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.columnconfigure(2, weight=1)
        self.accent = tk.Frame(self, width=4)
        self.accent.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        self.step = ttk.Label(self, text="", style="Step.TLabel")
        self.step.grid(row=0, column=1, sticky="w", padx=(0, 14))
        self.text = ttk.Label(self, text="", justify="left", style="Card.TLabel")
        self.text.grid(row=0, column=2, sticky="ew")
        self.actions = ttk.Frame(self, style="Card.TFrame")
        self.actions.grid(row=0, column=3, sticky="e", padx=(12, 0))
        helpButton(self, app, topic).grid(row=0, column=4, sticky="e", padx=(8, 0))
        self.bind("<Configure>", lambda e: self.text.configure(wraplength=max(200, e.width - 460)))
        app.theme.onChange(lambda palette: self.accent.configure(background=palette["accent"]))
        self.current = None

    def show(self, step, text, actions=()):
        """actions: (label, command) buttons offered next to the guidance."""
        state = (step, text, tuple(label for label, _command in actions))
        if state == self.current:
            return
        self.current = state
        self.step.configure(text=step)
        self.text.configure(text=text)
        for child in self.actions.winfo_children():
            child.destroy()
        for label, command in actions:
            ttk.Button(self.actions, text=label, command=command).pack(side="left", padx=(8, 0))
        if actions:
            self.actions.grid()
        else:
            self.actions.grid_remove()


class ViewState:
    """Zoom and position shared by image views, so they always show the same part of the texture."""

    def __init__(self):
        self.zoom = 1.0
        self.centreX = 0.5
        self.centreY = 0.5
        self.views = []
        self.listeners = []  # called after every zoom or move

    def changed(self):
        for view in self.views:
            view.scheduleRedraw()
        for listener in self.listeners:
            listener()

    def reset(self):
        self.zoom, self.centreX, self.centreY = 1.0, 0.5, 0.5
        self.changed()


class ImageView(ttk.Frame):
    """Shows an image scaled to fit, with scroll-to-zoom, drag-to-move and double-click-to-fit."""

    def __init__(self, parent, theme, state, placeholder):
        super().__init__(parent)
        self.state = state
        state.views.append(self)
        self.image = None
        self.levels = []
        self.photo = None
        self.imageItem = None
        self.textItem = None
        self.lastView = None
        self.placeholder = placeholder
        self.dragStart = None
        self.redrawPending = False
        self.textColour = "#bdbdbd"

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.scheduleRedraw())
        self.canvas.bind("<MouseWheel>", lambda e: self.onWheel(e, e.delta > 0))
        # Linux reports the mouse wheel as buttons 4 and 5
        self.canvas.bind("<Button-4>", lambda e: self.onWheel(e, True))
        self.canvas.bind("<Button-5>", lambda e: self.onWheel(e, False))
        self.canvas.bind("<ButtonPress-1>", self.onPress)
        self.canvas.bind("<B1-Motion>", self.onDrag)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.state.reset())
        theme.onChange(self.onTheme)

    def onTheme(self, palette):
        self.canvas.configure(background=palette["canvas"])
        self.textColour = palette["canvasText"]
        self.lastView = None
        self.scheduleRedraw()

    def setImage(self, image, placeholder=None):
        self.image = image
        # Half, quarter... size copies, so zoomed-out views resize from a nearby size instead of the full texture
        self.levels = [(1, image)] if image is not None else []
        while image is not None and min(self.levels[-1][1].size) >= 512:
            factor, level = self.levels[-1]
            self.levels.append((factor * 2, level.reduce(2)))
        if placeholder is not None:
            self.placeholder = placeholder
        self.canvas.configure(cursor="fleur" if image is not None else "")
        self.lastView = None
        self.scheduleRedraw()

    def scheduleRedraw(self):
        if not self.redrawPending:
            self.redrawPending = True
            self.after_idle(self.redraw)

    def scale(self):
        """Screen pixels per image pixel at the current zoom, or None without an image."""
        if self.image is None or self.canvas.winfo_width() < 2:
            return None
        return self.geometry()[0]

    def geometry(self):
        """Returns (scale, left, top) of the visible area in image pixels, keeping it inside the image."""
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        imageWidth, imageHeight = self.image.size
        scale = min(width / imageWidth, height / imageHeight) * self.state.zoom
        viewWidth, viewHeight = width / scale, height / scale

        def clampCentre(centre, view, size):
            if view >= size:
                return 0.5
            return min(max(centre, view / 2 / size), 1 - view / 2 / size)

        self.state.centreX = clampCentre(self.state.centreX, viewWidth, imageWidth)
        self.state.centreY = clampCentre(self.state.centreY, viewHeight, imageHeight)
        left = self.state.centreX * imageWidth - viewWidth / 2
        top = self.state.centreY * imageHeight - viewHeight / 2
        return scale, left, top

    def redraw(self):
        self.redrawPending = False
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 2 or height < 2:
            return

        if self.image is None:
            self.canvas.delete("all")
            self.imageItem = None
            self.lastView = None
            self.textItem = self.canvas.create_text(width / 2, height / 2, text=self.placeholder, fill=self.textColour,
                                                    width=max(width - 60, 100), justify="center", font="AppBody")
            return

        scale, left, top = self.geometry()
        view = (width, height, round(scale, 6), round(left, 3), round(top, 3), id(self.image))
        if view == self.lastView:
            return
        self.lastView = view

        imageWidth, imageHeight = self.image.size
        box = (max(left, 0), max(top, 0), min(left + width / scale, imageWidth), min(top + height / scale, imageHeight))
        size = (max(1, round((box[2] - box[0]) * scale)), max(1, round((box[3] - box[1]) * scale)))

        # From 100% up, every texture pixel is shown sharp
        if scale >= 1:
            shown = self.image.resize(size, Image.Resampling.NEAREST, box=box)
        else:
            factor, level = next(((f, l) for f, l in reversed(self.levels) if scale * f >= 1), self.levels[0])
            levelBox = tuple(value / factor for value in box)
            shown = level.resize(size, Image.Resampling.BILINEAR, box=levelBox)

        if self.photo is not None and self.photo.width() == size[0] and self.photo.height() == size[1]:
            self.photo.paste(shown)
        else:
            self.photo = ImageTk.PhotoImage(shown)
        position = ((box[0] - left) * scale, (box[1] - top) * scale)
        if self.textItem is not None:
            self.canvas.delete(self.textItem)
            self.textItem = None
        if self.imageItem is None:
            self.imageItem = self.canvas.create_image(*position, image=self.photo, anchor="nw")
        else:
            self.canvas.itemconfigure(self.imageItem, image=self.photo)
            self.canvas.coords(self.imageItem, *position)

    def onWheel(self, event, zoomIn):
        if self.image is None:
            return
        scale, left, top = self.geometry()
        pointX, pointY = left + event.x / scale, top + event.y / scale

        factor = 1.25 if zoomIn else 0.8
        self.state.zoom = min(max(self.state.zoom * factor, 1.0), 64.0)

        # Keep the pixel under the pointer in place
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        imageWidth, imageHeight = self.image.size
        newScale = min(width / imageWidth, height / imageHeight) * self.state.zoom
        self.state.centreX = (pointX - event.x / newScale + width / newScale / 2) / imageWidth
        self.state.centreY = (pointY - event.y / newScale + height / newScale / 2) / imageHeight
        self.state.changed()

    def onPress(self, event):
        self.dragStart = (event.x, event.y, self.state.centreX, self.state.centreY)

    def onDrag(self, event):
        if self.image is None or self.dragStart is None:
            return
        scale, _left, _top = self.geometry()
        startX, startY, centreX, centreY = self.dragStart
        imageWidth, imageHeight = self.image.size
        self.state.centreX = centreX - (event.x - startX) / scale / imageWidth
        self.state.centreY = centreY - (event.y - startY) / scale / imageHeight
        self.state.changed()


class HelpWindow(tk.Toplevel):
    """All help topics: a list on the left, the chosen topic on the right."""

    INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*\s][^*]*\*)")

    def __init__(self, app, topic, welcome=False):
        super().__init__(app)
        self.app = app
        self.title("Image Colour help")
        app.theme.track(self)

        screenWidth, screenHeight = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(1100, int(screenWidth * 0.7)), min(820, int(screenHeight * 0.8))
        self.geometry(f"{width}x{height}+{(screenWidth - width) // 2}+{max((screenHeight - height) // 4, 0)}")
        self.minsize(min(640, screenWidth - 40), min(420, screenHeight - 80))

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        self.topics = ttk.Treeview(outer, show="tree", selectmode="browse")
        self.topics.column("#0", width=240, stretch=False)
        for key, title, _body in HelpText.TOPICS:
            self.topics.insert("", "end", iid=key, text=title)
        self.topics.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        self.topics.bind("<<TreeviewSelect>>", lambda _e: self.render(self.topics.selection()[0]) if self.topics.selection() else None)

        textFrame = ttk.Frame(outer)
        textFrame.grid(row=0, column=1, sticky="nsew")
        textFrame.columnconfigure(0, weight=1)
        textFrame.rowconfigure(0, weight=1)
        self.text = tk.Text(textFrame, wrap="word", borderwidth=0, highlightthickness=0, padx=22, pady=16, cursor="arrow",
                            font="AppBody", spacing1=3, spacing3=7)
        scroll = AutoScrollbar(textFrame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        bottom = ttk.Frame(outer)
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.showAtStart = tk.BooleanVar(value=app.settings["showWelcome"])
        ttk.Checkbutton(bottom, text="Show Getting started when the app opens", variable=self.showAtStart, style="Switch.TCheckbutton",
                        command=lambda: app.settings.__setitem__("showWelcome", self.showAtStart.get())).pack(side="left")
        ttk.Button(bottom, text="Close", command=self.destroy, style="Accent.TButton" if welcome else "TButton").pack(side="right")

        app.theme.onChange(self.onTheme)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.showTopic(topic)

    def onTheme(self, palette):
        if not self.winfo_exists():
            return
        self.text.configure(background=palette["surface"], foreground=palette["foreground"], selectbackground=palette["selection"])
        self.text.tag_configure("title", font="AppTitle", foreground=palette["strong"], spacing3=12)
        self.text.tag_configure("h2", font="AppSubtitle", foreground=palette["heading"], spacing1=16, spacing3=6)
        self.text.tag_configure("bold", font="AppStrong", foreground=palette["strong"])
        self.text.tag_configure("italic", font="AppItalic", foreground=palette["muted"])
        self.text.tag_configure("code", font="AppMono", foreground=palette["codeText"], background=palette["code"])
        self.text.tag_configure("marker", foreground=palette["heading"], font="AppStrong")
        self.text.tag_configure("item", lmargin1=12, lmargin2=36, tabs=("36",))

    def showTopic(self, topic):
        self.topics.selection_set(topic)
        self.topics.see(topic)
        self.render(topic)
        self.lift()
        self.focus_set()

    def render(self, topic):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", HelpText.TOPIC_TITLES[topic] + "\n", "title")
        for line in HelpText.topicBody(topic).splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("## "):
                self.text.insert("end", stripped[3:] + "\n", "h2")
                continue
            tags = ()
            bullet = re.match(r"^(- |\d+\. )", stripped)
            if bullet:
                marker = "•\t" if bullet.group(1) == "- " else bullet.group(1).strip() + "\t"
                self.text.insert("end", marker, ("item", "marker"))
                stripped = stripped[len(bullet.group(1)):]
                tags = ("item",)
            for part in self.INLINE.split(stripped):
                if part.startswith("**") and part.endswith("**") and len(part) > 4:
                    self.text.insert("end", part[2:-2], tags + ("bold",))
                elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                    self.text.insert("end", " " + part[1:-1] + " ", tags + ("code",))
                elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                    self.text.insert("end", part[1:-1], tags + ("italic",))
                elif part:
                    self.text.insert("end", part, tags)
            self.text.insert("end", "\n", tags)
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)
