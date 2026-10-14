import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Mask categories, in the order the mask classifier labels them
MASK_CHANNELS = ("red", "green", "blue", "white", "black")

SHADE_KEYS = {"detail", "highlights", "shadows", "reference"}
LEGACY_KEYS = {"flip_below", "lift", "lift_mode"}
CHANNEL_KEYS = {"colour", "method"} | SHADE_KEYS | LEGACY_KEYS
RULE_KEYS = {"below", "add", "multiply"}
METHODS = ("shade", "legacy")
LIFT_MODES = ("first", "all")


class ProfileError(Exception):
    pass


@dataclass(frozen=True)
class LiftRule:
    below: int
    add: tuple
    multiply: float = 1


@dataclass(frozen=True)
class ChannelSpec:
    style: str = "keep"  # keep | grey | tint
    colour: tuple = None
    method: str = "shade"
    # shade method
    detail: float = 1.0
    highlights: float = 1.0
    shadows: float = 1.0
    reference: float = None  # None = median of the region
    # legacy method
    flipBelow: int = 0
    lift: tuple = ()
    liftMode: str = "first"


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    channels: dict


def loadProfiles(path):
    """
    Reads the profile config file and returns a dict of fully resolved profiles.
    Every profile starts from [defaults], then applies its `extends` chain, then its own settings.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ProfileError(f"Profile file not found: {path}")
    return parseProfiles(text, path)


def parseProfiles(text, path):
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ProfileError(f"{path}: {e}")

    colours = data.get("colours", {})
    presets = data.get("presets", {})
    defaults = data.get("defaults", {})
    rawProfiles = data.get("profiles", {})

    if not rawProfiles:
        raise ProfileError(f"{path}: no [profiles.<name>] sections defined")

    checkKeys(defaults, set(MASK_CHANNELS), "[defaults]")

    def resolveColour(value, where):
        if isinstance(value, str):
            if value not in colours:
                raise ProfileError(f"{where}: unknown colour '{value}' (add it to [colours])")
            value = colours[value]
        if not (isinstance(value, list) and len(value) == 3 and all(isinstance(v, int) and 0 <= v <= 255 for v in value)):
            raise ProfileError(f"{where}: colour must be [r, g, b] with values 0-255, or a name from [colours]")
        return tuple(value)

    def channelLayer(value, where):
        if isinstance(value, str):
            if value in ("keep", "grey"):
                return {"style": value}
            if value in presets:
                if not isinstance(presets[value], dict):
                    raise ProfileError(f"[presets] {value}: must be a table")
                return channelLayer(presets[value], f"[presets] {value}")
            raise ProfileError(f"{where}: '{value}' is not 'keep', 'grey' or a name from [presets]")
        if isinstance(value, dict):
            checkKeys(value, CHANNEL_KEYS, where)
            return {"style": "tint", **value}
        raise ProfileError(f"{where}: expected 'keep', 'grey', a preset name or a table")

    def buildChannel(merged, where):
        if merged is None or merged["style"] != "tint":
            return ChannelSpec(style=merged["style"] if merged else "keep")
        if "colour" not in merged:
            raise ProfileError(f"{where}: tinted channel needs a colour")

        method = merged.get("method", "shade")
        if method not in METHODS:
            raise ProfileError(f"{where}: method must be one of {METHODS}")
        wrongKeys = set(merged) & (LEGACY_KEYS if method == "shade" else SHADE_KEYS)
        if wrongKeys:
            raise ProfileError(f"{where}: {sorted(wrongKeys)} can't be used with method = \"{method}\"")

        if method == "shade":
            numbers = {}
            for key in ("detail", "highlights", "shadows"):
                value = merged.get(key, 1.0)
                if not isinstance(value, (int, float)) or value < 0:
                    raise ProfileError(f"{where}: {key} must be a number >= 0")
                numbers[key] = float(value)
            reference = merged.get("reference", "auto")
            if reference == "auto":
                reference = None
            elif not (isinstance(reference, (int, float)) and 0 <= reference <= 1):
                raise ProfileError(f"{where}: reference must be \"auto\" or a number from 0 to 1")
            return ChannelSpec(
                style="tint",
                colour=resolveColour(merged["colour"], where),
                method="shade",
                reference=reference,
                **numbers,
            )

        liftMode = merged.get("lift_mode", "first")
        if liftMode not in LIFT_MODES:
            raise ProfileError(f"{where}: lift_mode must be one of {LIFT_MODES}")

        rules = []
        for i, rule in enumerate(merged.get("lift", [])):
            ruleWhere = f"{where} lift[{i}]"
            if not isinstance(rule, dict) or "below" not in rule:
                raise ProfileError(f"{ruleWhere}: each rule needs at least 'below'")
            checkKeys(rule, RULE_KEYS, ruleWhere)
            add = rule.get("add", 0)
            if isinstance(add, int):
                add = [add] * 3
            if not (isinstance(add, list) and len(add) == 3 and all(isinstance(v, int) for v in add)):
                raise ProfileError(f"{ruleWhere}: 'add' must be a number or [r, g, b]")
            rules.append(LiftRule(int(rule["below"]), tuple(add), rule.get("multiply", 1)))

        return ChannelSpec(
            style="tint",
            colour=resolveColour(merged["colour"], where),
            method="legacy",
            flipBelow=int(merged.get("flip_below", 0)),
            lift=tuple(rules),
            liftMode=liftMode,
        )

    def chainFor(name, seen=()):
        if name in seen:
            raise ProfileError(f"Circular 'extends': {' -> '.join(seen + (name,))}")
        if name not in rawProfiles:
            raise ProfileError(f"Unknown profile '{name}'" + (f" (extended by '{seen[-1]}')" if seen else ""))
        raw = rawProfiles[name]
        checkKeys(raw, set(MASK_CHANNELS) | {"description", "extends"}, f"[profiles.{name}]")
        parent = raw.get("extends")
        return (chainFor(parent, seen + (name,)) if parent else []) + [(f"profiles.{name}", raw)]

    profiles = {}
    for name in rawProfiles:
        layers = [("defaults", defaults)] + chainFor(name)
        channels = {}
        for channel in MASK_CHANNELS:
            merged = None
            for layerName, raw in layers:
                if channel in raw:
                    layer = channelLayer(raw[channel], f"[{layerName}] {channel}")
                    bothTint = merged is not None and merged["style"] == "tint" and layer["style"] == "tint"
                    if not bothTint:
                        merged = layer
                    elif layer.get("method", merged.get("method", "shade")) != merged.get("method", "shade"):
                        # Switching method: the inherited settings belong to the other method, only keep the colour
                        merged = {"colour": merged["colour"], **layer} if "colour" in merged else layer
                    else:
                        merged = {**merged, **layer}
            channels[channel] = buildChannel(merged, f"[profiles.{name}] {channel}")
        profiles[name] = Profile(name, rawProfiles[name].get("description", ""), channels)

    return profiles


PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def isValidProfileName(name):
    return bool(PROFILE_NAME_PATTERN.match(name))


def formatNumber(value):
    return repr(round(float(value), 3))


def channelToToml(spec):
    if spec.style in ("keep", "grey"):
        return f'"{spec.style}"'

    fields = [f"colour = [{', '.join(str(v) for v in spec.colour)}]"]
    if spec.method == "legacy":
        fields.insert(0, 'method = "legacy"')
        if spec.flipBelow:
            fields.append(f"flip_below = {spec.flipBelow}")
        if spec.lift:
            if spec.liftMode != "first":
                fields.append(f'lift_mode = "{spec.liftMode}"')
            rules = []
            for rule in spec.lift:
                text = f"below = {rule.below}, add = [{', '.join(str(v) for v in rule.add)}]"
                if rule.multiply != 1:
                    text += f", multiply = {rule.multiply}"
                rules.append(f"    {{ {text} }},")
            fields.append("lift = [\n" + "\n".join(rules) + "\n]")
    else:
        for key in ("detail", "highlights", "shadows"):
            value = getattr(spec, key)
            if value != 1.0:
                fields.append(f"{key} = {formatNumber(value)}")
        if spec.reference is not None:
            fields.append(f"reference = {formatNumber(spec.reference)}")

    return "{ " + ", ".join(fields) + " }"


def profileToToml(profile):
    """A self-contained [profiles.<name>] block that lists every channel, so [defaults] doesn't affect it."""
    lines = [f"[profiles.{profile.name}]", f"description = {json.dumps(profile.description)}"]
    for channel in MASK_CHANNELS:
        lines.append(f"{channel} = {channelToToml(profile.channels[channel])}")
    return "\n".join(lines) + "\n"


def saveProfile(path, profile):
    """
    Adds the profile to the file, or replaces the existing profile with that name.
    The rest of the file, comments included, is left as it is. Nothing is written if the result doesn't load.
    """
    if not isValidProfileName(profile.name):
        raise ProfileError(f"'{profile.name}' can't be used as a profile name: use only letters, digits, _ and -")

    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    block = profileToToml(profile)

    lines = text.splitlines(keepends=True)
    header = f"[profiles.{profile.name}]"
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)

    if start is None:
        newText = text.rstrip("\n") + "\n\n" + block if text.strip() else block
    else:
        end = start + 1
        while end < len(lines):
            line = lines[end].strip()
            if line.startswith("[") and not line.startswith(f"[profiles.{profile.name}."):
                break
            end += 1
        # Keep the blank lines and comments that lead into the next section
        while end - 1 > start and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
            end -= 1
        newText = "".join(lines[:start]) + block + "".join(lines[end:])

    parseProfiles(newText, path)

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(newText, encoding="utf-8")
    os.replace(temporary, path)


def checkKeys(table, allowed, where):
    unknown = set(table) - allowed
    if unknown:
        raise ProfileError(f"{where}: unknown setting(s) {sorted(unknown)}; expected any of {sorted(allowed)}")
