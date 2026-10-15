import concurrent.futures
import functools
import multiprocessing
import os
import queue
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import numpy as np
from PIL import Image

import ColourHandler
import FileHandler as File
import SystemSupport
from GuiWidgets import (AutoScrollbar, GuideBanner, HelpWindow, ImageView, STATUS_STYLES, Settings, TabBar, Theme, Tooltip, ViewState,
                        helpButton)
from ProfileHandler import MASK_CHANNELS, ChannelSpec, Profile, ProfileError, isValidProfileName, loadProfiles, saveProfile

CHANNEL_LABELS = {"red": "Red", "green": "Green", "blue": "Blue", "white": "White", "black": "Black"}
CC_SWATCHES = {"red": "#ff0000", "green": "#00ff00", "blue": "#0000ff", "white": "#ffffff", "black": "#000000"}

ACTION_KEEP = "Keep original"
ACTION_TINT = "Recolour"
ACTION_GREY = "Use grey texture"
ACTION_LEGACY = "Recolour (legacy formula)"
ACTIONS = [ACTION_KEEP, ACTION_TINT, ACTION_GREY]

DEFAULT_COLOUR = (128, 128, 128)
EXPERIMENTAL_MARK = " (experimental)"
DETECTED_THREADS = SystemSupport.detectThreads()
# Upper limit for the thread choice when detection fails
UNDETECTED_THREAD_LIMIT = 256
AUTO_RENDER_DELAY_MS = 250
# Previews use every PREVIEW_STEP-th pixel in both directions, unless Full resolution is on
PREVIEW_STEP = 2
# Darkens everything outside the part highlighted by Show
DIM_TABLE = (np.arange(256) * 0.18 + 10).astype(np.uint8)


def profileLabel(profile):
    """The profile's name as profile lists show it."""
    return profile.name + (EXPERIMENTAL_MARK if profile.experimental else "")


def profileName(label):
    return label.removesuffix(EXPERIMENTAL_MARK)


def toHex(colour):
    return "#%02x%02x%02x" % tuple(colour)


def parseColour(text):
    """Accepts #RRGGBB or 'R, G, B'. Returns a tuple, or None if the text isn't a colour."""
    text = text.strip()
    try:
        if text.startswith("#") and len(text) == 7:
            return tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))
        parts = [int(part) for part in text.replace(",", " ").split()]
        if len(parts) == 3 and all(0 <= part <= 255 for part in parts):
            return tuple(parts)
    except ValueError:
        pass
    return None


def imageSize(path):
    try:
        return cachedImageSize(str(path), os.path.getmtime(path))
    except OSError:
        return None


@functools.lru_cache(maxsize=4096)
def cachedImageSize(path, _modified):
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None


def openFolder(path):
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def statusLabel(parent, text=""):
    return ttk.Label(parent, text=text, justify="left")


def setStatusText(label, text, kind=""):
    label.configure(text=text, style=STATUS_STYLES[kind])


def sectionTitle(parent, app, text, topic):
    """A section heading with its help button, for use as a LabelFrame's label."""
    frame = ttk.Frame(parent)
    ttk.Label(frame, text=text, style="Heading.TLabel").pack(side="left")
    helpButton(frame, app, topic).pack(side="left", padx=(8, 0))
    return frame


class TextureFilesDialog(tk.Toplevel):
    """Lets the user pick the base, grey and CC texture of one texture set by hand."""

    def __init__(self, app, parent, entry=None, title="Choose texture files"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(True, False)
        app.theme.track(self)
        self.result = None
        self.textureRoot = app.root

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Pick the three files that belong together", style="Subtitle.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="Check that the names match: they should only differ by _a and _cc at the end.", style="Muted.TLabel",
                  wraplength=620).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 14))

        self.paths = {}
        rows = (("base", "Base texture", File.BASE_FOLDER), ("grey", "Grey texture", File.GREY_FOLDER), ("mask", "CC texture", File.MASK_FOLDER))
        for row, (key, label, folder) in enumerate(rows, start=2):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            variable = tk.StringVar(value=str(getattr(entry, key)) if entry and getattr(entry, key) else "")
            variable.trace_add("write", lambda *_: self.validate())
            self.paths[key] = variable
            ttk.Entry(frame, textvariable=variable, width=70).grid(row=row, column=1, sticky="ew", pady=4)
            ttk.Button(frame, text="Browse…", command=lambda k=key, f=folder: self.browse(k, f)).grid(row=row, column=2, padx=(8, 0), pady=4)

        self.message = ttk.Label(frame, text="", wraplength=620)
        self.message.grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=3, sticky="e", pady=(16, 0))
        self.okButton = ttk.Button(buttons, text="Use these files", style="Accent.TButton", command=self.accept)
        self.okButton.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.validate()
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def browse(self, key, folder):
        # Start where the current file is, otherwise in the program's folder (its texture folder when there is one)
        current = self.paths[key].get().strip()
        if current and Path(current).parent.is_dir():
            start = Path(current).parent
        else:
            start = File.textureFolder(self.textureRoot, folder)
            start = start if start.is_dir() else self.textureRoot
        path = filedialog.askopenfilename(parent=self, initialdir=str(start),
                                          filetypes=[("Images", " ".join("*" + ext for ext in sorted(File.IMAGE_EXTENSIONS))), ("All files", "*")])
        if path:
            self.paths[key].set(str(Path(path)))

    def validate(self):
        paths = {key: Path(variable.get()) for key, variable in self.paths.items() if variable.get().strip()}
        missing = [name for key, name in (("base", "base"), ("grey", "grey"), ("mask", "CC")) if key not in paths or not paths[key].is_file()]
        if missing:
            setStatusText(self.message, f"Choose the {', '.join(missing)} texture with Browse….", "muted")
            self.okButton.state(["disabled"])
            return
        sizes = {imageSize(path) for path in paths.values()}
        if len(sizes) != 1 or None in sizes:
            setStatusText(self.message, "✕ These files are different sizes, so they can't be combined. Choose files of the same size.", "failed")
            self.okButton.state(["disabled"])
            return
        width, height = sizes.pop()
        setStatusText(self.message, f"✓ All three files are {width} × {height}.", "success")
        self.okButton.state(["!disabled"])

    def accept(self):
        base = Path(self.paths["base"].get())
        self.result = File.TextureEntry(base.stem, base=base, grey=Path(self.paths["grey"].get()), mask=Path(self.paths["mask"].get()))
        self.destroy()


class ChannelRow:
    """The controls for one CC colour in the profile editor."""

    def __init__(self, editor, parent, row, channel):
        self.editor = editor
        self.channel = channel
        self.colour = None
        self.legacySpec = None
        self.measuredColour = None
        self.palette = None
        label = CHANNEL_LABELS[channel]

        swatchFrame = ttk.Frame(parent)
        swatchFrame.grid(row=row, column=0, sticky="w", padx=(0, 16), pady=4)
        self.ccSwatch = tk.Frame(swatchFrame, width=18, height=18, background=CC_SWATCHES[channel], highlightthickness=1)
        self.ccSwatch.pack(side="left", padx=(0, 8))
        ttk.Label(swatchFrame, text=label).pack(side="left")

        self.areaLabel = ttk.Label(parent, text="–", width=15, style="Muted.TLabel")
        self.areaLabel.grid(row=row, column=1, sticky="w", padx=(0, 8))

        self.showButton = ttk.Button(parent, text="Show", width=6, command=lambda: editor.showArea(channel))
        self.showButton.grid(row=row, column=2, sticky="w", padx=(0, 16))
        Tooltip(self.showButton, f"Highlight where {label.lower()} is on the texture, on the left. Press again to hide it.")

        self.action = tk.StringVar(value=ACTION_KEEP)
        self.actionBox = ttk.Combobox(parent, textvariable=self.action, values=ACTIONS, state="readonly", width=22)
        self.actionBox.grid(row=row, column=3, sticky="w", padx=(0, 16))
        self.actionBox.bind("<<ComboboxSelected>>", lambda _e: self.onActionChanged())

        colourFrame = ttk.Frame(parent)
        colourFrame.grid(row=row, column=4, sticky="w", padx=(0, 16))
        self.chip = tk.Label(colourFrame, width=5, height=1, borderwidth=0, highlightthickness=1, cursor="hand2")
        self.chip.pack(side="left", padx=(0, 8), ipady=3)
        self.chip.bind("<Button-1>", lambda _e: self.pickColour())
        Tooltip(self.chip, "Click to pick the new colour.")
        self.colourText = tk.StringVar()
        self.colourEntry = ttk.Entry(colourFrame, textvariable=self.colourText, width=9)
        self.colourEntry.pack(side="left")
        self.colourEntry.bind("<Return>", lambda _e: self.onColourTyped())
        self.colourEntry.bind("<FocusOut>", lambda _e: self.onColourTyped())
        Tooltip(self.colourEntry, "Or type a colour code: #RRGGBB, or three numbers from 0 to 255.")

        self.numbers = {}
        for column, key in enumerate(("detail", "highlights", "shadows"), start=5):
            variable = tk.StringVar(value="1.0")
            variable.trace_add("write", lambda *_: self.editor.settingsChanged())
            spinbox = ttk.Spinbox(parent, textvariable=variable, from_=0.0, to=3.0, increment=0.1, width=6, format="%.1f")
            spinbox.grid(row=row, column=column, sticky="w", padx=(0, 16))
            self.numbers[key] = (variable, spinbox)
        self.ccStrength = tk.BooleanVar(value=True)
        self.ccStrengthBox = ttk.Checkbutton(parent, variable=self.ccStrength, command=self.editor.settingsChanged)
        self.ccStrengthBox.grid(row=row, column=8, sticky="w", padx=(0, 16))
        Tooltip(self.ccStrengthBox, f"On: less paint where {label.lower()} is faint in the CC texture, like the game, so worn edges "
                                    "show the grey texture. Off: the whole part is painted evenly.")

        editor.app.theme.onChange(self.onTheme)
        self.updateState()

    def onTheme(self, palette):
        self.palette = palette
        self.ccSwatch.configure(background=CC_SWATCHES[self.channel], highlightbackground=palette["chipBorder"])
        self.updateState()

    def fineTuningWidgets(self):
        return [spinbox for _variable, spinbox in self.numbers.values()] + [self.ccStrengthBox]

    def setStats(self, coverage, measuredColour):
        self.measuredColour = measuredColour
        if coverage == 0:
            setStatusText(self.areaLabel, "Not used here", "muted")
            self.showButton.state(["disabled"])
        else:
            percent = coverage * 100
            setStatusText(self.areaLabel, f"{percent:.1f}% of texture" if percent < 10 else f"{percent:.0f}% of texture")
            self.showButton.state(["!disabled"])

    def onActionChanged(self):
        if self.action.get() == ACTION_TINT and self.colour is None:
            self.colour = self.measuredColour or DEFAULT_COLOUR
        if self.action.get() != ACTION_LEGACY:
            self.legacySpec = None
            self.actionBox.configure(values=ACTIONS)
        self.updateState()
        self.editor.settingsChanged()

    def recolouring(self):
        return self.action.get() in (ACTION_TINT, ACTION_LEGACY)

    def pickColour(self):
        if not self.recolouring():
            self.editor.setStatus(f"Set Action to Recolour first to choose a new colour for {CHANNEL_LABELS[self.channel].lower()}.", "warning")
            return
        chosen = colorchooser.askcolor(color=toHex(self.colour or DEFAULT_COLOUR), parent=self.editor,
                                       title=f"New colour for {CHANNEL_LABELS[self.channel].lower()}")
        if chosen and chosen[0]:
            self.colour = tuple(int(round(v)) for v in chosen[0])
            self.updateState()
            self.editor.settingsChanged()

    def onColourTyped(self):
        if not self.recolouring():
            return
        colour = parseColour(self.colourText.get())
        if colour is None:
            self.editor.setStatus(f"✕ '{self.colourText.get()}' isn't a colour code. Type #RRGGBB, or three numbers from 0 to 255.", "failed")
            self.updateState()
            return
        if colour != self.colour:
            self.colour = colour
            self.updateState()
            self.editor.settingsChanged()

    def updateState(self):
        if self.palette is None:
            return
        action = self.action.get()
        if self.recolouring() and self.colour:
            self.chip.configure(background=toHex(self.colour), highlightbackground=self.palette["chipBorder"], cursor="hand2")
            self.colourText.set(toHex(self.colour))
            self.colourEntry.state(["!disabled"])
        else:
            self.chip.configure(background=self.palette["chipEmpty"], highlightbackground=self.palette["chipEmpty"], cursor="")
            self.colourText.set("")
            self.colourEntry.state(["disabled"])

        for _variable, spinbox in self.numbers.values():
            spinbox.state(["!disabled"] if action == ACTION_TINT else ["disabled"])
        self.ccStrengthBox.state(["!disabled"] if action == ACTION_TINT else ["disabled"])

    def reset(self):
        self.legacySpec = None
        self.actionBox.configure(values=ACTIONS)
        self.action.set(ACTION_KEEP)
        self.colour = None
        for variable, _spinbox in self.numbers.values():
            variable.set("1.0")
        self.ccStrength.set(True)
        self.updateState()

    def load(self, spec):
        self.reset()
        if spec.style == "grey":
            self.action.set(ACTION_GREY)
        elif spec.style == "tint" and spec.method == "legacy":
            self.legacySpec = spec
            self.actionBox.configure(values=ACTIONS + [ACTION_LEGACY])
            self.action.set(ACTION_LEGACY)
        elif spec.style == "tint":
            self.action.set(ACTION_TINT)
            for key, (variable, _spinbox) in self.numbers.items():
                variable.set(f"{getattr(spec, key):.1f}")
            self.ccStrength.set(spec.ccStrength)
        self.colour = spec.colour
        self.updateState()

    def spec(self):
        """Builds the ChannelSpec for this row; raises ValueError with a message for the user."""
        action = self.action.get()
        if action == ACTION_KEEP:
            return ChannelSpec(style="keep")
        if action == ACTION_GREY:
            return ChannelSpec(style="grey")
        if action == ACTION_LEGACY:
            return ChannelSpec(**{**self.legacySpec.__dict__, "colour": self.colour})

        values = {}
        for key, (variable, _spinbox) in self.numbers.items():
            try:
                values[key] = float(variable.get())
            except ValueError:
                values[key] = -1
            if not 0 <= values[key] <= 3:
                raise ValueError(f"✕ {key.capitalize()} for {CHANNEL_LABELS[self.channel].lower()} must be a number from 0 to 3.")
        return ChannelSpec(style="tint", colour=self.colour, method="shade", ccStrength=self.ccStrength.get(), **values)


class EditorTab(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, padding=16)
        self.app = app
        self.textureSet = None
        self.arrays = None
        self.images = {}
        self.areaImages = {}
        self.renderCache = {}
        self.dirty = False
        self.loading = False
        self.rendering = False
        self.renderAgain = False
        self.autoRenderJob = None
        self.lastRenderedProfile = None
        self.savedName = None
        self.setEntries = []
        self.shownArea = None
        self.inputBeforeArea = "base"

        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        self.guide = GuideBanner(self, app, "editor")
        self.guide.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        # Texture set
        textureFrame = ttk.Frame(self)
        textureFrame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        textureFrame.columnconfigure(3, weight=1)
        ttk.Label(textureFrame, text="Texture set", width=12).grid(row=0, column=0, sticky="w")
        self.setChoice = tk.StringVar()
        self.setBox = ttk.Combobox(textureFrame, textvariable=self.setChoice, state="readonly", width=34)
        self.setBox.grid(row=0, column=1, padx=(0, 8))
        self.setBox.bind("<<ComboboxSelected>>", lambda _e: self.onSetChosen())
        Tooltip(self.setBox, "The texture to try your colours on. The list shows the texture sets found on the Batch tab.")
        chooseButton = ttk.Button(textureFrame, text="Choose files…", command=self.chooseFiles)
        chooseButton.grid(row=0, column=2, padx=(0, 16))
        Tooltip(chooseButton, "Pick a base, grey and CC texture from anywhere.")
        self.fileNames = ttk.Label(textureFrame, text="No texture set loaded yet.", style="Muted.TLabel")
        self.fileNames.grid(row=0, column=3, sticky="w")

        # Profile
        profileFrame = ttk.Frame(self)
        profileFrame.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        profileFrame.columnconfigure(6, weight=1)
        ttk.Label(profileFrame, text="Profile", width=12).grid(row=0, column=0, sticky="w")
        self.profileChoice = tk.StringVar()
        self.profileBox = ttk.Combobox(profileFrame, textvariable=self.profileChoice, state="readonly", width=34)
        self.profileBox.grid(row=0, column=1, padx=(0, 8))
        self.profileBox.bind("<<ComboboxSelected>>", lambda _e: self.onProfileChosen())
        Tooltip(self.profileBox, "Open a saved profile to view or change it.")
        newButton = ttk.Button(profileFrame, text="New profile", command=self.newProfile)
        newButton.grid(row=0, column=2, padx=(0, 24))
        Tooltip(newButton, "Start again with every CC colour set to Keep original.")
        ttk.Label(profileFrame, text="Name").grid(row=0, column=3, padx=(0, 8))
        self.profileName = tk.StringVar()
        self.profileName.trace_add("write", lambda *_: self.settingsChanged(affectsRender=False))
        nameEntry = ttk.Entry(profileFrame, textvariable=self.profileName, width=24)
        nameEntry.grid(row=0, column=4, padx=(0, 16))
        Tooltip(nameEntry, "Letters, digits, _ and - only, for example dark_angels. Shown in the Batch tab's Profile list and in output folder names.")
        ttk.Label(profileFrame, text="Description").grid(row=0, column=5, padx=(0, 8))
        self.description = tk.StringVar()
        self.description.trace_add("write", lambda *_: self.settingsChanged(affectsRender=False))
        ttk.Entry(profileFrame, textvariable=self.description).grid(row=0, column=6, sticky="ew", padx=(0, 16))
        self.saveButton = ttk.Button(profileFrame, text="Save profile", command=self.saveProfile)
        self.saveButton.grid(row=0, column=7)

        # CC colours
        channelFrame = ttk.LabelFrame(self, labelwidget=sectionTitle(self, app, "CC colours", "texture-sets"), padding=(14, 8))
        channelFrame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        channelFrame.columnconfigure(9, weight=1)
        headers = (
            ("CC colour", "The colour that marks a part of the armour in the CC texture."),
            ("Area", "How much of the loaded texture this CC colour covers."),
            ("", ""),
            ("Action", "Keep original copies the part from the base texture. Recolour paints it in the new colour. "
                       "Use grey texture copies it from the grey texture."),
            ("New colour", "What clean, undamaged paint will look like. Scratches and grime are added on top."),
            ("Detail", "How strongly scratches and grime show. 1 matches the original; 0 is a flat colour."),
            ("Highlights", "How far scratches and worn edges can lighten the colour. 1 matches the original."),
            ("Shadows", "How far grime and crevices can darken the colour. 1 matches the original."),
            ("CC strength", "On: less paint where the CC colour is faint, like the game, so worn edges show the grey texture. "
                            "Off: the whole part is painted evenly."),
        )
        self.fineTuningHeaders = []
        for column, (text, tip) in enumerate(headers):
            header = ttk.Label(channelFrame, text=text, style="Heading.TLabel")
            header.grid(row=0, column=column, sticky="w", padx=(0, 16), pady=(0, 6))
            if tip:
                Tooltip(header, tip)
            if column >= 5:
                self.fineTuningHeaders.append(header)
        self.rows = {channel: ChannelRow(self, channelFrame, row, channel) for row, channel in enumerate(MASK_CHANNELS, start=1)}

        fineFrame = ttk.Frame(channelFrame)
        fineFrame.grid(row=0, column=9, rowspan=2, sticky="ne")
        self.fineTuning = tk.BooleanVar(value=app.settings["fineTuning"])
        ttk.Checkbutton(fineFrame, text="Fine-tuning", style="Switch.TCheckbutton", variable=self.fineTuning,
                        command=self.onFineTuningToggled).pack(side="left")
        helpButton(fineFrame, app, "fine-tuning").pack(side="left", padx=(8, 0))
        self.onFineTuningToggled(save=False)

        # Render
        renderFrame = ttk.Frame(self)
        renderFrame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        renderFrame.columnconfigure(3, weight=1)
        self.renderButton = ttk.Button(renderFrame, text="Render", style="Accent.TButton", width=12, command=self.render)
        self.renderButton.grid(row=0, column=0, padx=(0, 12))
        Tooltip(self.renderButton, "Show the result of the current settings on the right. Shortcut: F5.")
        self.autoRender = tk.BooleanVar(value=app.settings["autoRender"])
        autoSwitch = ttk.Checkbutton(renderFrame, text="Render automatically", style="Switch.TCheckbutton", variable=self.autoRender,
                                     command=self.onAutoRenderToggled)
        autoSwitch.grid(row=0, column=1, padx=(0, 20))
        Tooltip(autoSwitch, "Update the result shortly after every change, without pressing Render.")
        self.fullResolution = tk.BooleanVar(value=app.settings["fullResolution"])
        fullSwitch = ttk.Checkbutton(renderFrame, text="Full resolution", style="Switch.TCheckbutton", variable=self.fullResolution,
                                     command=self.onFullResolutionToggled)
        fullSwitch.grid(row=0, column=2, padx=(0, 20))
        Tooltip(fullSwitch, "Always render every pixel of the texture. Off renders a half-size preview, about four times faster, "
                            "and every pixel once you zoom in past 50%. Actual size shows one screen pixel per rendered pixel. "
                            "The Batch tab always renders at full resolution.")
        self.status = statusLabel(renderFrame)
        self.status.grid(row=0, column=3, sticky="w")
        viewHelp = ttk.Frame(renderFrame)
        viewHelp.grid(row=0, column=4, sticky="e")
        ttk.Label(viewHelp, text="Scroll to zoom · drag to move · double-click for whole texture or actual size", style="Muted.TLabel").pack(side="left")
        helpButton(viewHelp, app, "views").pack(side="left", padx=(8, 0))

        # Previews
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.grid(row=5, column=0, sticky="nsew")
        self.viewState = ViewState()
        self.viewState.minScale = self.actualSizeScale()
        self.viewState.listeners.append(self.onViewChanged)
        self.zoomRenderJob = None
        self.lastRenderFull = False

        left = ttk.Frame(panes)
        switch = ttk.Frame(left)
        switch.pack(fill="x", pady=(0, 6))
        self.inputChoice = tk.StringVar(value="base")
        for value, text in (("base", "Base texture"), ("grey", "Grey texture"), ("mask", "CC texture")):
            ttk.Radiobutton(switch, text=text, value=value, variable=self.inputChoice, command=self.showInput,
                            style="Toggle.Toolbutton").pack(side="left", padx=(0, 6))
        self.areaNote = ttk.Label(switch, text="", style="Muted.TLabel")
        self.areaNote.pack(side="left", padx=(8, 0))
        self.inputView = ImageView(left, app.theme, self.viewState, "Choose a texture set at the top to see it here.")
        self.inputView.pack(fill="both", expand=True)

        right = ttk.Frame(panes)
        resultHeader = ttk.Frame(right)
        resultHeader.pack(fill="x", pady=(0, 6))
        ttk.Label(resultHeader, text="Result", style="Heading.TLabel", padding=(0, 6)).pack(side="left")
        self.resultView = ImageView(right, app.theme, self.viewState, "The result appears here when you press Render.")
        self.resultView.pack(fill="both", expand=True)

        panes.add(left, weight=1)
        panes.add(right, weight=1)

        self.updateControls()

    # Guidance

    def updateGuide(self):
        recolouring = any(row.recolouring() or row.action.get() == ACTION_GREY for row in self.rows.values())
        if self.arrays is None:
            self.guide.show("Step 1 of 4", "Choose a Texture set to try your colours on. Pick one that shows all the parts you want to recolour.",
                            [("Choose files…", self.chooseFiles)])
        elif not recolouring:
            self.guide.show("Step 2 of 4", "For each part you want to change, set Action to Recolour and pick a New colour. "
                                           "Not sure which part a CC colour is? Press Show next to it.")
        elif self.rendering:
            self.guide.show("Rendering", "The result appears on the right in a moment.")
        elif self.lastRenderedProfile is None:
            self.guide.show("Step 3 of 4", "Press Render to see the result of your settings.")
        elif self.dirty or not self.savedName:
            self.guide.show("Step 4 of 4", "Happy with the result? Type a Name and press Save profile. "
                                           "If not, change the colours and render again.")
        else:
            self.guide.show("Saved", f"The profile {self.savedName} is saved. Use it on the Batch tab, or keep adjusting it.",
                            [("Go to Batch", self.app.showBatch)])

    # Texture sets

    def setTextureEntries(self, entries):
        self.setEntries = [entry for entry in entries if entry.complete]
        self.setBox.configure(values=[entry.name for entry in self.setEntries])

    def onSetChosen(self):
        index = self.setBox.current()
        if index >= 0:
            self.loadTextureSet(self.setEntries[index])

    def chooseFiles(self):
        dialog = TextureFilesDialog(self.app, self, self.textureSet)
        self.wait_window(dialog)
        if dialog.result:
            self.loadTextureSet(dialog.result)

    def loadTextureSet(self, entry):
        textureSet = entry.textureSet()
        self.setStatus(f"Loading {textureSet.name}…")
        self.app.runInBackground(lambda: self.readTextures(textureSet), lambda result: self.onTexturesLoaded(textureSet, result))

    @staticmethod
    def readTextures(textureSet):
        # PNG decoding releases the GIL, so the three files load in parallel
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            base, grey, mask = pool.map(ColourHandler.extractImage, (textureSet.base, textureSet.grey, textureSet.mask))
        if not (base.shape == grey.shape == mask.shape):
            raise ValueError("the base, grey and CC textures are different sizes")
        labels = ColourHandler.classifyMask(mask)
        stats = ColourHandler.regionStats(base, labels)
        images = {key: Image.fromarray(array.astype("uint8")) for key, array in (("base", base), ("grey", grey), ("mask", mask))}
        # Every second pixel in both directions, for quick previews
        preview = tuple(array[::PREVIEW_STEP, ::PREVIEW_STEP] for array in (base, grey, mask, labels))
        # Work out each part's grey lightness now, so the first preview is as quick as the rest
        previewCache = {}
        for index in range(len(MASK_CHANNELS)):
            selected = preview[3] == index
            if selected.any():
                lightness = ColourHandler.greyLightness(preview[1][selected])
                previewCache[index] = (lightness, np.median(lightness))
        return base, grey, mask, labels, stats, images, preview, previewCache

    def onTexturesLoaded(self, textureSet, result):
        if isinstance(result, Exception):
            self.setStatus(f"✕ Couldn't load {textureSet.name}: {result}. Choose another texture set.", "failed")
            return
        base, grey, mask, labels, stats, images, self.previewArrays, self.previewCache = result
        self.renderCache = {}
        self.textureSet = textureSet
        self.arrays = (base, grey, mask, labels)
        self.images = images
        self.areaImages = {}
        self.fileNames.configure(text=f"{textureSet.base.name}   ·   {textureSet.grey.name}   ·   {textureSet.mask.name}", style="Muted.TLabel")
        names = [entry.name for entry in self.setEntries]
        self.setChoice.set(textureSet.name if textureSet.name in names else "")

        for channel, row in self.rows.items():
            row.setStats(*stats[channel])
        self.inputChoice.set("base")
        self.showInput()
        self.resultView.setImage(None, "The result appears here when you press Render.")
        self.lastRenderedProfile = None
        if ColourHandler.maskIsCopy(base, grey, mask):
            self.setStatus(f"⚠ The CC texture of {textureSet.name} is a copy of its base texture, so it marks no parts. "
                           "Rendering keeps this texture unchanged.", "warning")
        else:
            self.setStatus(f"Loaded {textureSet.name}.")
        self.updateControls()
        self.scheduleAutoRender()

    def showInput(self):
        self.areaNote.configure(text="")
        self.setShownArea(None)
        if self.arrays is not None:
            self.inputView.setImage(self.images[self.inputChoice.get()])

    def setShownArea(self, channel):
        self.shownArea = channel
        for rowChannel, row in self.rows.items():
            row.showButton.configure(text="Hide" if rowChannel == channel else "Show")

    def showArea(self, channel):
        if self.arrays is None:
            return
        if self.shownArea == channel:
            self.inputChoice.set(self.inputBeforeArea)
            self.showInput()
            return
        if self.shownArea is None:
            self.inputBeforeArea = self.inputChoice.get() or "base"
        if channel not in self.areaImages:
            labels = self.arrays[3]
            base = np.asarray(self.images["base"])
            selected = (labels == MASK_CHANNELS.index(channel))[..., None]
            self.areaImages[channel] = Image.fromarray(np.where(selected, base, DIM_TABLE[base]))
        self.inputChoice.set("")
        self.inputView.setImage(self.areaImages[channel])
        self.setShownArea(channel)
        self.areaNote.configure(text=f"Showing where {CHANNEL_LABELS[channel].lower()} is: the bright part. Press Hide to go back.")

    # Profiles

    def setProfiles(self, profiles):
        self.profileBox.configure(values=[profileLabel(profile) for profile in profiles.values()])

    def showSavedName(self):
        profile = self.app.profiles.get(self.savedName)
        self.profileChoice.set(profileLabel(profile) if profile else "")

    def confirmDiscard(self, doing):
        if not self.dirty:
            return True
        return messagebox.askokcancel("Discard your changes?", f"{doing} replaces the settings you haven't saved.", parent=self, default="cancel")

    def onProfileChosen(self):
        name = profileName(self.profileChoice.get())
        if not self.confirmDiscard(f"Opening {name}"):
            self.showSavedName()
            return
        profile = self.app.profiles[name]
        self.loading = True
        for channel, row in self.rows.items():
            row.load(profile.channels[channel])
        self.profileName.set(profile.name)
        self.description.set(profile.description)
        self.loading = False
        self.dirty = False
        self.savedName = name
        self.markResultStale()
        if profile.experimental:
            self.setStatus(f"Opened {name}. It's experimental: it hasn't been checked against finished textures yet.", "warning")
        else:
            self.setStatus(f"Opened {name}.")
        self.updateGuide()
        self.scheduleAutoRender()

    def newProfile(self):
        if not self.confirmDiscard("Starting a new profile"):
            return
        self.loading = True
        for row in self.rows.values():
            row.reset()
        self.profileName.set("")
        self.description.set("")
        self.profileChoice.set("")
        self.loading = False
        self.dirty = False
        self.savedName = None
        self.markResultStale()
        self.setStatus("Started a new profile.")
        self.updateGuide()

    def buildProfile(self):
        """Returns the Profile described by the editor; raises ValueError with a message for the user."""
        name = self.profileName.get().strip() or "unsaved"
        channels = {channel: row.spec() for channel, row in self.rows.items()}
        # Saving over a profile keeps its experimental mark
        experimental = name in self.app.profiles and self.app.profiles[name].experimental
        return Profile(name, self.description.get().strip(), channels, experimental)

    def saveProfile(self):
        name = self.profileName.get().strip()
        if not name:
            self.setStatus("✕ Type a Name for the profile first, then press Save profile.", "failed")
            return
        if not isValidProfileName(name):
            self.setStatus(f"✕ '{name}' can't be used as a name. Use only letters, digits, _ and -, for example dark_angels.", "failed")
            return
        try:
            profile = self.buildProfile()
        except ValueError as e:
            self.setStatus(str(e), "failed")
            return
        if name in self.app.profiles and name != self.savedName:
            if not messagebox.askokcancel("Replace the saved profile?", f"A profile called {name} already exists. Saving replaces its settings with these.",
                                          parent=self, default="cancel"):
                return
        try:
            saveProfile(self.app.profilesPath, profile)
        except (ProfileError, OSError) as e:
            self.setStatus(f"✕ Not saved: {e}", "failed")
            return
        self.app.reloadProfiles()
        self.savedName = name
        self.showSavedName()
        self.dirty = False
        self.setStatus(f"✓ Saved {name}.", "success")
        self.updateGuide()

    # Rendering

    def settingsChanged(self, affectsRender=True):
        if self.loading:
            return
        self.dirty = True
        if affectsRender:
            self.markResultStale()
            self.scheduleAutoRender()
        self.updateGuide()

    def markResultStale(self):
        if self.lastRenderedProfile is not None:
            self.lastRenderedProfile = None
            if not self.autoRender.get():
                self.setStatus("⚠ Settings changed since the last render. Press Render to update the result.", "warning")

    def onAutoRenderToggled(self):
        self.app.settings["autoRender"] = self.autoRender.get()
        self.scheduleAutoRender()

    def scheduleAutoRender(self):
        if not self.autoRender.get() or self.arrays is None:
            return
        if self.autoRenderJob:
            self.after_cancel(self.autoRenderJob)
        self.autoRenderJob = self.after(AUTO_RENDER_DELAY_MS, self.autoRenderNow)

    def autoRenderNow(self):
        self.autoRenderJob = None
        if self.rendering:
            self.renderAgain = True
        elif self.lastRenderedProfile is None:
            self.render(quiet=True)

    def render(self, quiet=False):
        if self.arrays is None or self.rendering:
            return
        try:
            profile = self.buildProfile()
        except ValueError as e:
            if not quiet:
                self.setStatus(str(e), "failed")
            return
        self.rendering = True
        self.renderAgain = False
        self.updateControls()
        self.setStatus("Rendering…")
        full = self.needsFullResolution()
        base, grey, mask, labels = self.arrays if full else self.previewArrays
        cache = self.renderCache if full else self.previewCache
        size = self.images["base"].size
        started = time.perf_counter()

        def work():
            result = Image.fromarray(ColourHandler.imageRecolour(base, grey, mask, profile, labels, cache))
            # Shown at full size, so both pictures stay in step when zooming
            return result if full else result.resize(size, Image.Resampling.NEAREST)

        def done(result):
            self.rendering = False
            if isinstance(result, Exception):
                self.setStatus(f"✕ Render failed: {result}", "failed")
                self.updateControls()
                return
            self.resultView.setImage(result)
            # Settings may have changed while rendering
            try:
                current = self.buildProfile().channels
            except ValueError:
                current = None
            self.lastRenderFull = full
            if current == profile.channels and (full or not self.needsFullResolution()):
                self.lastRenderedProfile = profile
                if full == self.fullResolution.get():
                    what = "Rendered" if full else "Rendered a half-size preview"
                else:
                    what = "Rendered every pixel for the zoomed-in view"
                self.setStatus(f"✓ {what} in {time.perf_counter() - started:.1f} s with the current settings.", "success")
            else:
                self.lastRenderedProfile = None
                self.setStatus("⚠ Settings changed while rendering. Press Render to update the result.", "warning")
            self.updateControls()
            if self.renderAgain or (self.lastRenderedProfile is None and self.autoRender.get()):
                self.scheduleAutoRender()
            self.onViewChanged()

        self.app.runInBackground(work, done)

    def needsFullResolution(self):
        """Full resolution when it's switched on, or when the view is zoomed in far enough to show a preview's missing detail."""
        if self.fullResolution.get():
            return True
        scale = self.resultView.scale() or self.inputView.scale()
        return scale is not None and scale * PREVIEW_STEP > 1

    def onViewChanged(self):
        # Zooming in on a preview renders the same settings again at full resolution, shortly after the zoom stops
        if self.zoomRenderJob:
            self.after_cancel(self.zoomRenderJob)
            self.zoomRenderJob = None
        if self.lastRenderedProfile is not None and not self.lastRenderFull and self.needsFullResolution():
            self.zoomRenderJob = self.after(AUTO_RENDER_DELAY_MS, self.renderForZoom)

    def renderForZoom(self):
        self.zoomRenderJob = None
        # While rendering, the finished render checks the zoom again
        if not self.rendering and self.lastRenderedProfile is not None and not self.lastRenderFull and self.needsFullResolution():
            self.render(quiet=True)

    def actualSizeScale(self):
        """Actual size: one screen pixel per rendered pixel, so every texture pixel at full resolution and every preview pixel otherwise."""
        return 1.0 if self.fullResolution.get() else 1 / PREVIEW_STEP

    def onFullResolutionToggled(self):
        self.app.settings["fullResolution"] = self.fullResolution.get()
        self.viewState.setMinScale(self.actualSizeScale())
        self.markResultStale()
        self.scheduleAutoRender()

    def onFineTuningToggled(self, save=True):
        show = self.fineTuning.get()
        if save:
            self.app.settings["fineTuning"] = show
        widgets = self.fineTuningHeaders + [widget for row in self.rows.values() for widget in row.fineTuningWidgets()]
        for widget in widgets:
            widget.grid() if show else widget.grid_remove()

    def updateControls(self):
        self.renderButton.state(["!disabled"] if self.arrays is not None and not self.rendering else ["disabled"])
        if self.arrays is None:
            self.setStatus("")
        self.updateGuide()

    def setStatus(self, text, kind=""):
        setStatusText(self.status, text, kind)


class BatchTab(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, padding=16)
        self.app = app
        self.entries = {}
        self.batch = {}
        self.batchProfiles = {}
        self.outputDirs = {}
        self.executor = None
        self.stopping = False
        self.runFinished = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.guide = GuideBanner(self, app, "batch")
        self.guide.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        folderFrame = ttk.Frame(self)
        folderFrame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        folderFrame.columnconfigure(1, weight=1)
        ttk.Label(folderFrame, text="Texture folder").grid(row=0, column=0, padx=(0, 12))
        self.folderLabel = ttk.Label(folderFrame, text="", style="Muted.TLabel")
        self.folderLabel.grid(row=0, column=1, sticky="w")
        selectButton = ttk.Button(folderFrame, text="Select folder…", command=self.changeFolder)
        selectButton.grid(row=0, column=2, padx=(8, 0))
        Tooltip(selectButton, f"Choose the folder to scan: the one that holds the {File.BASE_FOLDER}, {File.GREY_FOLDER} and "
                              f"{File.MASK_FOLDER} folders.")
        rescanButton = ttk.Button(folderFrame, text="Rescan", command=self.rescan)
        rescanButton.grid(row=0, column=3, padx=(8, 0))
        Tooltip(rescanButton, "Look for texture files again, after adding or renaming files.")

        panes = ttk.PanedWindow(self, orient="vertical")
        panes.grid(row=2, column=0, sticky="nsew")

        # Texture sets found
        foundFrame = ttk.LabelFrame(panes, labelwidget=sectionTitle(panes, app, "Texture sets found", "texture-sets"), padding=10)
        foundFrame.columnconfigure(0, weight=1)
        foundFrame.rowconfigure(0, weight=1)
        self.foundTree = self.makeTree(foundFrame, (("name", "Name", 170), ("base", "Base texture", 230), ("grey", "Grey texture", 230),
                                                    ("mask", "CC texture", 230), ("size", "Size", 120), ("status", "Status", 230)))
        self.foundEmpty = ttk.Label(foundFrame, style="Muted.TLabel", justify="center",
                                    text=f"No texture sets found.\nPut your textures in the {File.BASE_FOLDER}, {File.GREY_FOLDER} and "
                                         f"{File.MASK_FOLDER} folders of the texture folder, then press Rescan.")
        foundButtons = ttk.Frame(foundFrame)
        foundButtons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        foundButtons.columnconfigure(3, weight=1)
        self.addButton = ttk.Button(foundButtons, text="Add selected to batch", command=self.addSelected)
        self.addButton.grid(row=0, column=0, padx=(0, 8))
        Tooltip(self.addButton, "Add the selected texture sets to the batch below. Hold Ctrl or Shift to select several.")
        changeFilesButton = ttk.Button(foundButtons, text="Change files…", command=self.changeFiles)
        changeFilesButton.grid(row=0, column=1, padx=(0, 8))
        Tooltip(changeFilesButton, "Pick the right files for the selected texture set, if its names don't match.")
        editorButton = ttk.Button(foundButtons, text="Open in profile editor", command=self.openInEditor)
        editorButton.grid(row=0, column=2, padx=(0, 8))
        Tooltip(editorButton, "Try colours on the selected texture set in the Profile editor.")
        self.foundMessage = statusLabel(foundButtons)
        self.foundMessage.grid(row=0, column=3, sticky="w", padx=(8, 0))
        self.foundTree.bind("<Double-1>", lambda _e: self.addSelected())

        # Batch
        batchFrame = ttk.LabelFrame(panes, labelwidget=sectionTitle(panes, app, "Batch", "batch"), padding=10)
        batchFrame.columnconfigure(0, weight=1)
        batchFrame.rowconfigure(0, weight=1)
        self.batchTree = self.makeTree(batchFrame, (("name", "Name", 170), ("base", "Base texture", 210), ("grey", "Grey texture", 210),
                                                    ("mask", "CC texture", 210), ("profile", "Profile", 170), ("status", "Status", 330)))
        self.batchEmpty = ttk.Label(batchFrame, style="Muted.TLabel", justify="center",
                                    text="The batch is empty.\nSelect texture sets above and press Add selected to batch.")
        self.batchTree.bind("<<TreeviewSelect>>", lambda _e: self.updateControls())
        batchButtons = ttk.Frame(batchFrame)
        batchButtons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.removeButton = ttk.Button(batchButtons, text="Remove selected", command=self.removeSelected)
        self.removeButton.pack(side="left", padx=(0, 8))
        self.clearButton = ttk.Button(batchButtons, text="Clear batch", command=self.clearBatch)
        self.clearButton.pack(side="left")
        self.applyButton = ttk.Button(batchButtons, text="Use for all", command=self.applyProfile)
        self.applyButton.pack(side="right")
        Tooltip(self.applyButton, "Give the selected texture sets this profile, or every texture set if none are selected. "
                                  "Texture sets can each have their own profile, for example one for armour and one for shoulder pads.")
        self.profileChoice = tk.StringVar()
        self.profileChoice.trace_add("write", lambda *_: self.updateControls())
        self.profileBox = ttk.Combobox(batchButtons, textvariable=self.profileChoice, state="readonly", width=26)
        self.profileBox.pack(side="right", padx=(0, 8))
        Tooltip(self.profileBox, "The colours to use. Texture sets you add get this profile. Make your own in the Profile editor.")
        ttk.Label(batchButtons, text="Profile").pack(side="right", padx=(0, 8))

        panes.add(foundFrame, weight=3)
        panes.add(batchFrame, weight=2)

        # Run
        runFrame = ttk.Frame(self)
        runFrame.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        runFrame.columnconfigure(7, weight=1)
        ttk.Label(runFrame, text="Threads").grid(row=0, column=2, padx=(0, 8))
        self.maxThreads = DETECTED_THREADS or UNDETECTED_THREAD_LIMIT
        self.threads = tk.StringVar(value=str(DETECTED_THREADS or SystemSupport.FALLBACK_THREADS))
        self.threadsBox = ttk.Spinbox(runFrame, textvariable=self.threads, from_=1, to=self.maxThreads, increment=1, width=5)
        self.threadsBox.grid(row=0, column=3, padx=(0, 8))
        Tooltip(self.threadsBox, "How many textures render at the same time. More is faster; fewer keeps the computer responsive.")
        if DETECTED_THREADS:
            threadsNote = ttk.Label(runFrame, text=f"of {DETECTED_THREADS} on this processor", style="Muted.TLabel")
        else:
            threadsNote = ttk.Label(runFrame, text="⚠ Couldn't detect this processor's threads: choose how many to use", style="Warning.TLabel")
        threadsNote.grid(row=0, column=4, padx=(0, 24))
        self.runButton = ttk.Button(runFrame, text="Render", style="Accent.TButton", command=self.startBatch)
        self.runButton.grid(row=0, column=5, padx=(0, 8))
        self.stopButton = ttk.Button(runFrame, text="Stop batch", command=self.stopBatch)
        self.stopButton.grid(row=0, column=6, padx=(0, 16))
        Tooltip(self.stopButton, "Let the textures already rendering finish, and skip the rest.")
        self.progress = ttk.Progressbar(runFrame, mode="determinate")
        self.progress.grid(row=0, column=7, sticky="ew", padx=(0, 16))
        self.openButton = ttk.Button(runFrame, text="Open output folder", command=self.openOutput)
        self.openButton.grid(row=0, column=8)
        Tooltip(self.openButton, "Open the folder with the results of the latest run. "
                                 "After a run with several profiles, this opens the output folder that holds them.")
        self.status = statusLabel(self)
        self.status.grid(row=4, column=0, sticky="w", pady=(10, 0))

        app.theme.onChange(self.onTheme)
        self.updateControls()

    def onTheme(self, palette):
        for tree in (self.foundTree, self.batchTree):
            tree.tag_configure("failed", foreground=palette["failed"])
            tree.tag_configure("warning", foreground=palette["warning"])
            tree.tag_configure("success", foreground=palette["success"])

    @staticmethod
    def makeTree(parent, columns):
        tree = ttk.Treeview(parent, columns=[key for key, _text, _width in columns], show="headings", selectmode="extended")
        for key, text, width in columns:
            tree.heading(key, text=text, anchor="w")
            tree.column(key, width=width, minwidth=60, stretch=True, anchor="w")
        scroll = AutoScrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        return tree

    @staticmethod
    def showEmpty(label, tree, empty):
        if empty:
            label.place(in_=tree, relx=0.5, rely=0.55, anchor="center")
        else:
            label.place_forget()

    # Guidance

    def updateGuide(self):
        items = self.runItems()
        if self.running:
            self.guide.show("Rendering", "Your textures are being recoloured. You can keep working in the Profile editor while you wait.")
        elif not self.entries:
            self.guide.show("Get started", f"Put your textures in the {File.BASE_FOLDER}, {File.GREY_FOLDER} and {File.MASK_FOLDER} "
                                           "folders of the texture folder, then press Rescan. Textures somewhere else? "
                                           "Press Select folder… to scan that folder instead.",
                            [("Select folder…", self.changeFolder), ("Rescan", self.rescan)])
        elif self.runFinished and self.outputDirs:
            self.guide.show("Done", "Your textures are ready. Press Open output folder to see them, or add more texture sets and render again.",
                            [("Open output folder", self.openOutput)])
        elif not items:
            self.guide.show("Step 1 of 3", "Select the texture sets you want in Texture sets found, then press Add selected to batch.")
        elif self.missingProfiles(items):
            self.guide.show("Step 2 of 3", "Give every texture set a profile: choose a Profile under the batch and press "
                                           f"{self.applyButton.cget('text')}. Parts that need other colours, like shoulder pads, "
                                           "can have their own profile.",
                            [("Open Profile editor", self.app.showEditorTab)])
        else:
            what = f"the {len(self.batchTree.selection())} selected texture sets" if self.batchTree.selection() else "every texture set in the batch"
            used = sorted({self.batchProfiles[iid] for iid in items})
            folders = " for each profile" if len(used) > 1 else ""
            self.guide.show("Step 3 of 3", f"Press {self.runButton.cget('text')} to recolour {what} with {', '.join(used)}. "
                                           f"The results go into a new folder in output{folders}.")

    # Texture sets found

    def rescan(self):
        self.folderLabel.configure(text=str(self.app.root))
        self.foundTree.delete(*self.foundTree.get_children())
        self.entries = {}
        entries = File.scanTextureFolders(self.app.root)
        for entry in entries:
            iid = self.foundTree.insert("", "end")
            self.entries[iid] = entry
            self.showEntry(iid)
        self.app.editor.setTextureEntries(entries)
        self.showEmpty(self.foundEmpty, self.foundTree, not entries)
        if entries:
            problems = sum(1 for entry in entries if not self.entryStatus(entry)[3])
            checks = sum(1 for entry in entries if self.entryStatus(entry)[3] and entry.guessed)
            parts = [f"Found {len(entries)} texture set{'s' if len(entries) != 1 else ''}"]
            if checks:
                parts.append(f"{checks} to check")
            if problems:
                parts.append(f"{problems} with problems")
            self.setFoundMessage(", ".join(parts) + ".", "warning" if problems or checks else "muted")
        else:
            self.setFoundMessage("")
        self.updateControls()

    def entryStatus(self, entry):
        """Returns (status text, tag, size text, can be rendered)."""
        missing = [label for label, path in (("base", entry.base), ("grey", entry.grey), ("CC", entry.mask)) if path is None]
        sizes = {imageSize(path) for path in (entry.base, entry.grey, entry.mask) if path is not None}
        sizeText = " / ".join(f"{w} × {h}" for w, h in sizes) if None not in sizes else "Unreadable"
        if missing:
            return f"✕ Missing {' and '.join(missing)} texture", "failed", sizeText, False
        if None in sizes:
            return "✕ Can't read a file", "failed", sizeText, False
        if len(sizes) > 1:
            return "✕ Sizes differ", "failed", sizeText, False
        if entry.guessed:
            return "⚠ Check names; CC is a copy" if entry.maskIsCopy else "⚠ Check names", "warning", sizeText, True
        if entry.maskIsCopy:
            return "⚠ CC is a copy: saved unchanged", "warning", sizeText, True
        if entry.variantOf:
            return f"✓ Ready: extra CC for {entry.variantOf}", "", sizeText, True
        return "✓ Ready", "", sizeText, True

    def showEntry(self, iid):
        entry = self.entries[iid]
        status, tag, sizeText, _ok = self.entryStatus(entry)
        names = [path.name if path else "—" for path in (entry.base, entry.grey, entry.mask)]
        self.foundTree.item(iid, values=(entry.name, *names, sizeText, status), tags=(tag,) if tag else ())

    def selectedEntries(self):
        return [(iid, self.entries[iid]) for iid in self.foundTree.selection()]

    def changeFolder(self):
        folder = filedialog.askdirectory(parent=self, initialdir=str(self.app.root if self.app.root.is_dir() else File.PROJECT_DIR),
                                         title=f"Select the folder that holds {File.BASE_FOLDER}, {File.GREY_FOLDER} and {File.MASK_FOLDER}")
        if folder:
            self.app.root = Path(folder)
            self.rescan()

    def changeFiles(self):
        selected = self.selectedEntries()
        if len(selected) != 1:
            self.setFoundMessage("Select one texture set first, then press Change files….", "warning")
            return
        iid, entry = selected[0]
        dialog = TextureFilesDialog(self.app, self, entry, title=f"Change files of {entry.name}")
        self.wait_window(dialog)
        if dialog.result:
            self.entries[iid] = dialog.result
            self.showEntry(iid)
            self.app.editor.setTextureEntries(list(self.entries.values()))
            self.setFoundMessage(f"✓ Updated {dialog.result.name}.", "success")

    def openInEditor(self):
        selected = self.selectedEntries()
        if len(selected) != 1:
            self.setFoundMessage("Select one texture set first, then press Open in profile editor.", "warning")
            return
        _iid, entry = selected[0]
        status, _tag, _size, ok = self.entryStatus(entry)
        if not ok:
            self.setFoundMessage(f"✕ {entry.name} can't be opened: {status[2:].lower()}. Fix it with Change files… first.", "failed")
            return
        self.app.showEditor(entry)

    def setFoundMessage(self, text, kind=""):
        setStatusText(self.foundMessage, text, kind)

    # Batch

    def addSelected(self):
        selected = self.selectedEntries()
        if not selected:
            self.setFoundMessage("Select texture sets in the list first, then press Add selected to batch.", "warning")
            return
        inBatch = {(textureSet.base, textureSet.mask) for textureSet in self.batch.values()}
        profile = self.chosenProfile()
        added, skipped = 0, []
        for _iid, entry in selected:
            status, _tag, _size, ok = self.entryStatus(entry)
            if not ok:
                skipped.append(f"{entry.name} ({status[2:].lower()})")
                continue
            if (entry.base, entry.mask) in inBatch:
                skipped.append(f"{entry.name} (already in the batch)")
                continue
            textureSet = entry.textureSet()
            iid = self.batchTree.insert("", "end", values=(entry.name, entry.base.name, entry.grey.name, entry.mask.name,
                                                           profileLabel(self.app.profiles[profile]) if profile else "—", ""))
            self.batch[iid] = textureSet
            self.batchProfiles[iid] = profile
            inBatch.add((entry.base, entry.mask))
            added += 1

        text = f"Added {added} to the batch." if added else "Nothing added."
        if skipped:
            text += f" Not added: {', '.join(skipped)}."
        self.setFoundMessage(("✓ " if added and not skipped else "") + text, "failed" if skipped and not added else ("warning" if skipped else "success"))
        self.runFinished = False
        self.updateControls()

    def removeSelected(self):
        for iid in self.batchTree.selection():
            self.batchTree.delete(iid)
            del self.batch[iid]
            del self.batchProfiles[iid]
        self.runFinished = False
        self.updateControls()

    def clearBatch(self):
        self.batchTree.delete(*self.batchTree.get_children())
        self.batch = {}
        self.batchProfiles = {}
        self.runFinished = False
        self.updateControls()

    def runItems(self):
        selected = self.batchTree.selection()
        return list(selected) if selected else list(self.batchTree.get_children())

    def chosenProfile(self):
        """The name of the profile chosen under the batch, or "" if none is."""
        name = profileName(self.profileChoice.get())
        return name if name in self.app.profiles else ""

    def setProfiles(self, profiles):
        self.profileBox.configure(values=[profileLabel(profile) for profile in profiles.values()])
        name = profileName(self.profileChoice.get())
        self.profileChoice.set(profileLabel(profiles[name]) if name in profiles else "")
        for iid, name in self.batchProfiles.items():
            if name in profiles:
                self.batchTree.set(iid, "profile", profileLabel(profiles[name]))
        self.updateControls()

    def applyProfile(self):
        name = self.chosenProfile()
        if not name:
            self.setStatus("Choose a Profile first, then press this button again.", "warning")
            return
        for iid in self.runItems():
            self.batchProfiles[iid] = name
            self.batchTree.set(iid, "profile", profileLabel(self.app.profiles[name]))
        self.runFinished = False
        self.updateControls()

    def missingProfiles(self, items):
        return [iid for iid in items if self.batchProfiles.get(iid) not in self.app.profiles]

    # Running

    @property
    def running(self):
        return self.executor is not None

    def startBatch(self):
        items = self.runItems()
        if not items or self.missingProfiles(items):
            return
        try:
            threads = int(self.threads.get())
        except ValueError:
            threads = 0
        if not 1 <= threads <= self.maxThreads:
            self.setStatus(f"✕ Threads must be a whole number from 1 to {self.maxThreads}.", "failed")
            return

        self.started = datetime.now()
        # One folder per profile used, all named with this run's start time, so results never mix
        self.runProfiles = {iid: self.app.profiles[self.batchProfiles[iid]] for iid in items}
        self.outputDirs = {name: self.app.outputDir / File.outputFolderName(name, self.started)
                           for name in sorted({profile.name for profile in self.runProfiles.values()})}
        self.threadCount = threads
        self.pending = deque(items)
        self.active = {}
        self.doneCount = 0
        self.failedCount = 0
        self.stopping = False
        self.runFinished = False
        self.runTotal = len(items)

        # Clear statuses from earlier runs so results of separate runs never mix
        for iid in self.batchTree.get_children():
            self.setItemStatus(iid, "Waiting" if iid in items else "")
        self.progress.configure(maximum=len(items), value=0)

        # Spawn behaves the same on every OS and is safe alongside the GUI's threads
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=min(threads, len(items)),
                                                               mp_context=multiprocessing.get_context("spawn"))
        self.updateControls()
        self.fillWorkers()
        self.after(100, self.poll)

    def fillWorkers(self):
        while self.pending and len(self.active) < self.threadCount and not self.stopping:
            iid = self.pending.popleft()
            profile = self.runProfiles[iid]
            job = (self.batch[iid], profile, self.outputDirs[profile.name])
            self.active[self.executor.submit(ColourHandler.createRecolour, job)] = iid
            self.setItemStatus(iid, "Rendering…")
        self.showRunStatus()

    def poll(self):
        for future in [future for future in self.active if future.done()]:
            iid = self.active.pop(future)
            try:
                _target, error, note = future.result()
            except Exception as e:
                error, note = f"{type(e).__name__}: {e}", None
            if error:
                self.failedCount += 1
                self.setItemStatus(iid, f"✕ Failed: {error}", "failed")
            else:
                self.doneCount += 1
                self.setItemStatus(iid, f"✓ Done: {note}" if note else "✓ Done")
            self.progress.configure(value=self.doneCount + self.failedCount)

        self.fillWorkers()
        if self.active or (self.pending and not self.stopping):
            self.after(100, self.poll)
        else:
            self.finishBatch()

    def stopBatch(self):
        if self.running and not self.stopping:
            self.stopping = True
            self.updateControls()
            self.showRunStatus()

    def finishBatch(self):
        self.executor.shutdown(wait=False)
        self.executor = None
        notRendered = len(self.pending)
        for iid in self.pending:
            self.setItemStatus(iid, "⚠ Not rendered: the batch was stopped", "warning")
        self.pending = deque()

        elapsed = (datetime.now() - self.started).total_seconds()
        parts = [f"{self.doneCount} rendered"]
        if self.failedCount:
            parts.append(f"{self.failedCount} failed")
        if notRendered:
            parts.append(f"{notRendered} skipped because the batch was stopped")
        if self.failedCount:
            lead, kind = "✕ Finished with problems", "failed"
        elif notRendered:
            lead, kind = "⚠ Stopped", "warning"
        else:
            lead, kind = "✓ Finished", "success"
        self.outputDirs = {name: folder for name, folder in self.outputDirs.items() if folder.exists()}
        if len(self.outputDirs) == 1:
            where = f" Saved in {next(iter(self.outputDirs.values()))}."
        elif self.outputDirs:
            where = f" Saved in {len(self.outputDirs)} folders in {self.app.outputDir}, one per profile."
        else:
            where = ""
        self.setStatus(f"{lead}: {', '.join(parts)} in {elapsed:.1f} s.{where}", kind)
        self.runFinished = self.doneCount > 0
        self.updateControls()

    def showRunStatus(self):
        if not self.running:
            return
        finished = self.doneCount + self.failedCount
        if self.stopping:
            self.setStatus(f"⚠ Stopping: waiting for the {len(self.active)} texture sets in progress to finish. The rest won't be rendered.", "warning")
            return
        text = f"Rendering {self.runTotal} with {', '.join(self.outputDirs)}: {finished} finished, {len(self.active)} in progress"
        if self.failedCount:
            text += f", {self.failedCount} failed"
        self.setStatus(text + ".")

    def setItemStatus(self, iid, text, tag=""):
        self.batchTree.set(iid, "status", text)
        self.batchTree.item(iid, tags=(tag,) if tag else ())

    def openOutput(self):
        folders = [folder for folder in self.outputDirs.values() if folder.exists()]
        if len(folders) == 1:
            openFolder(folders[0])
        elif folders:
            openFolder(folders[0].parent)
        else:
            self.setStatus("Nothing has been rendered yet, so there's no output folder to open.", "warning")

    def updateControls(self):
        running = self.running
        items = self.runItems()
        selected = len(self.batchTree.selection())

        if selected:
            self.runButton.configure(text=f"Render {selected} selected")
        else:
            self.runButton.configure(text=f"Render all {len(items)}" if items else "Render")
        canRun = not running and items and not self.missingProfiles(items)
        self.runButton.state(["!disabled"] if canRun else ["disabled"])
        self.applyButton.configure(text=f"Use for {selected} selected" if selected else (f"Use for all {len(items)}" if items else "Use for all"))
        canApply = not running and items and self.chosenProfile()
        self.applyButton.state(["!disabled"] if canApply else ["disabled"])
        self.stopButton.state(["!disabled"] if running and not self.stopping else ["disabled"])
        for widget in (self.removeButton, self.clearButton, self.addButton):
            widget.state(["disabled"] if running else ["!disabled"])
        self.profileBox.state(["disabled"] if running else ["!disabled", "readonly"])
        self.threadsBox.state(["disabled"] if running else ["!disabled"])
        self.openButton.state(["!disabled"] if self.outputDirs else ["disabled"])
        self.showEmpty(self.batchEmpty, self.batchTree, not self.batch)
        self.updateGuide()

    def setStatus(self, text, kind=""):
        setStatusText(self.status, text, kind)


class App(tk.Tk):
    def __init__(self, root, profilesPath, settingsPath, outputDir):
        super().__init__()
        self.root = Path(root)
        self.outputDir = Path(outputDir)
        self.profilesPath = Path(profilesPath)
        self.profiles = {}
        self.backgroundResults = queue.Queue()
        self.helpWindow = None
        self.settings = Settings(settingsPath)

        self.title("Image Colour")
        self.fitToScreen()
        self.theme = Theme(self)
        self.theme.apply(self.settings["theme"] if self.settings["theme"] in ("dark", "light") else "dark")

        header = ttk.Frame(self, padding=(20, 14, 20, 6))
        header.pack(fill="x")
        titles = ttk.Frame(header)
        titles.pack(side="left")
        ttk.Label(titles, text="Image Colour", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Recolour Space Marine 2 armour textures with your own colours", style="Muted.TLabel").pack(anchor="w")
        self.darkMode = tk.BooleanVar(value=self.theme.mode == "dark")
        ttk.Checkbutton(header, text="Dark mode", style="Switch.TCheckbutton", variable=self.darkMode,
                        command=self.onThemeToggled).pack(side="right", padx=(16, 0))
        headerHelp = ttk.Button(header, text="Help", command=lambda: self.showHelp(self.currentTopic()))
        headerHelp.pack(side="right", padx=(8, 0))
        Tooltip(headerHelp, "Help on the tab you're on, with every other topic in the list. Shortcut: F1.")
        startButton = ttk.Button(header, text="Getting started", command=lambda: self.showHelp("getting-started"))
        startButton.pack(side="right")
        Tooltip(startButton, "A short guide to the whole app, from your first texture to finished results.")

        pages = ttk.Frame(self)
        self.tabBar = TabBar(self, self.theme, pages)
        self.tabBar.pack(fill="x", padx=20)
        ttk.Separator(self).pack(fill="x", padx=20)
        pages.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.editor = None
        self.batchTab = BatchTab(self, pages)
        self.editor = EditorTab(self, pages)
        self.tabBar.add(self.batchTab, "Batch")
        self.tabBar.add(self.editor, "Profile editor")

        self.bind("<F5>", lambda _e: self.editor.render() if self.tabBar.current is self.editor else None)
        self.bind("<F1>", lambda _e: self.showHelp(self.currentTopic()))
        self.protocol("WM_DELETE_WINDOW", self.onClose)
        self.after(50, self.pollBackground)

        self.reloadProfiles()
        self.batchTab.rescan()
        if self.settings["showWelcome"]:
            self.after(400, lambda: self.showHelp("getting-started", welcome=True))

    def fitToScreen(self):
        screenWidth, screenHeight = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = int(screenWidth * 0.85), int(screenHeight * 0.85)
        self.geometry(f"{width}x{height}+{(screenWidth - width) // 2}+{max((screenHeight - height) // 3, 0)}")
        self.minsize(min(1100, screenWidth - 40), min(700, screenHeight - 80))

    def onThemeToggled(self):
        mode = "dark" if self.darkMode.get() else "light"
        self.settings["theme"] = mode
        self.theme.apply(mode)

    def currentTopic(self):
        return "editor" if self.tabBar.current is self.editor else "batch"

    def showHelp(self, topic, welcome=False):
        if self.helpWindow is not None and self.helpWindow.winfo_exists():
            self.helpWindow.showTopic(topic)
        else:
            self.helpWindow = HelpWindow(self, topic, welcome=welcome)

    def reloadProfiles(self):
        try:
            self.profiles = loadProfiles(self.profilesPath)
        except ProfileError as e:
            self.profiles = {}
            messagebox.showerror("Profiles couldn't be loaded", f"{e}\n\nFix profiles.toml, then restart the app.", parent=self)
        self.batchTab.setProfiles(self.profiles)
        self.editor.setProfiles(self.profiles)
        self.batchTab.updateControls()

    def showEditor(self, entry):
        self.showEditorTab()
        self.editor.loadTextureSet(entry)

    def showEditorTab(self):
        self.tabBar.select(self.editor)

    def showBatch(self):
        self.tabBar.select(self.batchTab)

    def runInBackground(self, work, onDone):
        """Runs work() on a thread, then onDone(result or exception) on the GUI thread."""
        def run():
            try:
                result = work()
            except Exception as e:
                result = e
            self.backgroundResults.put((onDone, result))
        threading.Thread(target=run, daemon=True).start()

    def pollBackground(self):
        while not self.backgroundResults.empty():
            onDone, result = self.backgroundResults.get()
            onDone(result)
        self.after(50, self.pollBackground)

    def onClose(self):
        if self.batchTab.running:
            messagebox.showwarning("A batch is still rendering",
                                   "Press Stop batch on the Batch tab, wait for the textures in progress to finish, then close.", parent=self)
            return
        if self.editor.dirty:
            name = self.editor.profileName.get().strip() or "your profile"
            answer = messagebox.askyesnocancel("Save your profile changes?", f"Your changes to {name} aren't saved. Save them before closing?",
                                               parent=self, default="cancel")
            if answer is None:
                return
            if answer:
                self.editor.saveProfile()
                if self.editor.dirty:
                    self.showEditorTab()
                    return
        self.destroy()


def run(root, profilesPath, settingsPath, outputDir):
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(root, profilesPath, settingsPath, outputDir).mainloop()
