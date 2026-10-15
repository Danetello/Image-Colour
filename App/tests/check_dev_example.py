"""
Checks the app against hand-made example sets: every texture set is rendered with its profile and compared
with the matching image in the example's Final folder.

Run from the project folder:  App/venv/Scripts/python App/tests/check_dev_example.py [--only salamanders] [--texture "Soldier/*"] [--sheet comparison.png]
(App/venv/bin/python on Linux and macOS)
Exit code 0 means every check passed. Examples whose folder isn't there (Uniforms isn't in the repository) are skipped.
"""
import argparse
import dataclasses
import fnmatch
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ColourHandler  # noqa: E402
import FileHandler  # noqa: E402
from ProfileHandler import MASK_CHANNELS, loadProfiles  # noqa: E402

PROJECT_DIR = FileHandler.PROJECT_DIR
EXAMPLES_DIR = PROJECT_DIR / "Examples"
# Every team's textures: Shared/<uniform> holds what's the same for every team, <team>/<uniform> the team's own files
UNIFORMS = PROJECT_DIR / "Uniforms"
SHARED = UNIFORMS / "Shared"
GAME_UNIFORMS = ("Armour", "Engineer", "Grenadier", "Medic", "Officer", "Rain", "Scout", "Snow", "Soldier", "Tanker")
NEW_UNIFORMS = ("Paratrooper", "Pilot", "Sailor")

# Which profile each texture needs: the finished textures decide. Textures not listed use the example's default.
SALAMANDER_PROFILES = {
    **dict.fromkeys(("Grenadier_Backpack_Top", "Paratrooper_Jetpack", "Paratrooper_Shoulder_R", "Pilot_Shoulder_L", "Pilot_Shoulder_R",
                     "Rain_Backpack", "Sailor_Shoulder_L", "Scout_Caps", "Snow_Backpack_Cap", "Snow_Shoulder_R", "Tanker_Caps",
                     "Tanker_Shoulder_R"), "salamanders_black"),
    **dict.fromkeys(("Paratrooper_Cuirasse_Base", "Paratrooper_Cuirasse_Necks", "Paratrooper_Cuirasse_Plate", "Pilot_Helmet",
                     "Sailor_Cuirasse_Necks", "Sailor_Cuirasse_Plate"), "salamanders_gold_trim"),
    **dict.fromkeys(("Sailor_Shoulder_R", "Soldier_Backpack"), "salamanders_black_gold_trim"),
    **dict.fromkeys(("Armour_Helmet", "Grenadier_Belt", "Grenadier_Helmet_Cap", "Grenadier_Torso_1", "Grenadier_Torso_2", "Medic_Backpack",
                     "Rain_Belt", "Rain_Belt_Back", "Rain_Butt", "Rain_Cuirasse_1", "Rain_Cuirasse_2", "Rain_Hands", "Rain_Helmet", "Rain_Necks",
                     "Rain_Side_Vanity", "Scout_Torso", "Snow_Arms", "Snow_Helmet", "Snow_Shin", "Snow_Shoulder_Vanity", "Snow_Side_Plate",
                     "Snow_Torso_1", "Snow_Torso_2", "Snow_Torso_3", "Tanker_Helmet", "Tanker_Plate", "Tanker_Vanity"),
                    "salamanders_grey_unpainted"),
    **dict.fromkeys(("Grenadier_Shoulders", "Rain_Shoulders", "Snow_Shoulder_L"), "salamanders_black_grey_unpainted"),
    "Soldier_Shoulders": "salamanders_soldier_shoulders",
    "Officer_Shoulders": "salamanders_officer_shoulders",
    "Soldier_Helmet": "salamanders_soldier_helmet",
    "Sailor_Helmet": "salamanders_sailor_helmet",
    "Paratrooper_Helmet": "salamanders_paratrooper_helmet",
}
TEMPLAR_PROFILES = {
    **dict.fromkeys(("Grenadier_Shoulders", "Medic_Backpack", "Rain_Shoulders", "Snow_Shoulder_L", "Snow_Shoulder_R", "Soldier_Shoulders"),
                    "black_templars_shoulders"),
    **dict.fromkeys(("Soldier_Boots", "Soldier_Trims"), "black_templars_all_black"),
    "Scout/Soldier_Shoulders": "black_templars_scout_shoulders",
    "Officer_Shoulders": "black_templars_officer_shoulders",
    "Engineer_Skirt": "black_templars_engineer_skirt",
}

EXAMPLES = {
    "salamanders": {
        "folder": EXAMPLES_DIR / "Salamanders Pilot",
        "default": "salamanders",
        "profiles": SALAMANDER_PROFILES,
        "notes": "salamanders",
        "scan": {
            "sets": 6,
            "variants": {"Pilot_Helmet_checker"},
            "copies": {"Pilot_Arm"},
            "checkNames": {"Pilot_Arm"},
        },
    },
    "templars": {
        "folder": EXAMPLES_DIR / "Black Templars Soldier",
        "default": "black_templars",
        "profiles": TEMPLAR_PROFILES,
        "notes": "templars",
        "scan": {
            "sets": 5,
            "variants": set(),
            "copies": set(),
            # These base files are the grey textures, named as such (Soldier_Backpack_a.png)
            "checkNames": {"Soldier_Backpack", "Soldier_Boots"},
        },
    },
    # Uniforms isn't in the repository: these are skipped when it isn't there
    "finals_salamanders": {
        "folder": UNIFORMS / "Salamanders",
        "uniforms": GAME_UNIFORMS + NEW_UNIFORMS,
        "default": "salamanders",
        "profiles": SALAMANDER_PROFILES,
        "notes": "salamanders",
        "finalNames": {"Engineer_Skirt": "Engineer_Ski", "Scout/Soldier_Shoulders": "Scout_Shoulders"},
    },
    "finals_templars": {
        "folder": UNIFORMS / "Black Templars",
        "uniforms": GAME_UNIFORMS,
        "default": "black_templars",
        "profiles": TEMPLAR_PROFILES,
        "notes": "templars",
        "finalNames": {"Engineer_Skirt": "Engineer_Ski", "Scout/Soldier_Shoulders": "Scout_Shoulders"},
    },
    # The original game textures, made from the grey and CC textures only. Final holds the game texture.
    "ultramarines": {
        "folder": UNIFORMS / "Ultramarines",
        "uniforms": GAME_UNIFORMS,
        "default": "ultramarines",
        "profiles": {"Officer_Shoulders": "ultramarines_officer_shoulders"},
        "notes": "ultramarines",
        "fromGrey": True,
        # Ultramarine versions of the CC textures with team decals don't exist yet: use a team's, Salamander unless listed
        "ccFallback": UNIFORMS / "Salamanders",
        "ccFallbackFiles": {"Soldier/Soldier_Helmet_cc.png": UNIFORMS / "Black Templars"},
    },
}

# Textures that can't be checked, and why
SKIPPED = {
    "Grenadier_Helmet_Mouth": "the base texture is 2048 x 2048, the grey and CC textures 1024 x 1024",
    "Scout_Neck": "the base texture is 2048 x 1024, the grey and CC textures 2048 x 2048",
}

# Differences from the finals that are understood, per group of examples: {(texture, CC colour): reason}.
# A texture can be written as uniform/texture, and "*" matches any texture or CC colour.
# NOTES are intended: the finals were made with the old formula (colour * (1 - grey)), which made paint lighter on
# darker grey and darker on lighter grey. The app gives a part exactly its profile's colour, so it matches everywhere.
OLD_PAINT = "the old formula made paint lighter on darker grey and darker on lighter grey; the app keeps one colour"
OLD_DECAL = "the old formula made decals 220 x (1 - grey), from 116 to 196 in the finals; the app paints every decal decal_light (151)"
OLD_SILVER = "the old formula made silver 220 x (1 - grey), lighter on darker grey (correlation -1.0 over 16 textures); the app keeps one silver"
TINY_GREEN = "0.1% of the texture: near-black CC pixels that count as green. The finals differ (Salamanders 20, Templars 220)"

NOTES = {
    "salamanders": {
        **dict.fromkeys([(name, "red") for name in ("Pilot_Vanity_1", "Medic_Backpack", "Sailor_Cuirasse_Base", "Snow_Shoulder_Vanity",
                                                    "Grenadier_Belt", "Tanker_Plate")], OLD_PAINT),
        **dict.fromkeys([(name, "green") for name in ("Grenadier_Shoulders", "Paratrooper_Arm", "Sailor_Cuirasse_Necks", "Tanker_Plate",
                                                      "Tanker_Vanity")], OLD_DECAL),
        ("Grenadier_Belt", "green"): TINY_GREEN,
        **dict.fromkeys([(name, "blue") for name in ("Paratrooper_Helmet", "Soldier_Backpack")],
                        "gold_trim is measured from the game's gold [177, 140, 94]; the final used [176, 137, 89]"),
        ("Engineer_Skirt", "red"): "the final's skirt is a darker green [4, 39, 12]; the skirt uses the standard Salamander green on purpose",
    },
    "templars": {
        **dict.fromkeys([(name, "blue") for name in ("Soldier_Backpack", "Armour_Helmet", "Grenadier_Torso_2", "Rain_Necks", "Rain_Side_Vanity",
                                                     "Scout_Caps", "Snow_Backpack_Cap", "Snow_Torso_2", "Tanker_Caps", "Tanker_Helmet",
                                                     "Tanker_Shoulder_R", "Tanker_Vanity")], OLD_SILVER),
        **dict.fromkeys([(name, "green") for name in ("Tanker_Plate", "Tanker_Vanity")], OLD_DECAL),
        **dict.fromkeys([(name, "red") for name in ("Medic_Backpack", "Snow_Shoulder_L")], OLD_PAINT),
        ("Grenadier_Belt", "green"): TINY_GREEN,
    },
    "ultramarines": {
        ("*", "green"): "the game adds decals separately, so its textures have plain paint here; the app paints the decal",
        ("*", "black"): "the game texture isn't the grey texture here; black can only copy the grey texture",
        ("Engineer_Skirt", "*"): "the Ultramarine skirt has no paint: the game texture is the grey texture, so it needs no recolour",
        **dict.fromkeys([("Grenadier_Belt", "red"), ("Grenadier_Belt", "blue"), ("Grenadier_Shoulders", "red"), ("Grenadier_Shoulders", "blue"),
                         ("Rain_Shoulders", "blue"), ("Soldier_Backpack", "red"), ("Tanker_Helmet", "red"), ("Tanker_Vanity", "blue")],
                        "the game's own colour here is far from its usual paint [54, 68, 107] or gold [177, 140, 94]; "
                        "the Ultramarine profiles use the usual colours"),
        ("Soldier_Backpack", "blue"): "0.1% of the texture, painted Ultramarine blue in the game, not gold",
    },
}

# Differences no profile can reproduce, which need a decision. Listed as OPEN; they don't fail the check.
HAND_EDIT = "hand edit: the final paints only some pixels of this part green"
OPEN = {
    "salamanders": {
        ("Rain_Torso_Base", "red"): "the final wasn't recoloured: it's the Ultramarine texture",
        ("Tanker_Plate", "black"): HAND_EDIT + " (the Ultramarine heraldry, which is in the grey texture)",
        ("Paratrooper_Helmet", "black"): HAND_EDIT,
    },
}

# Pass limits
KEPT_IDENTICAL_MIN = 99.5  # % of the pixels the final left unchanged that must be unchanged here too
FLAT_COLOUR_MAX = 6  # largest allowed difference per channel between the median colours of a changed part
GAME_COLOUR_MAX = 24  # the same for the game's own textures: about twice the spread of the game's paint between textures
MIN_PART_PIXELS = 1000  # smaller parts aren't compared
SHEET_SIZE = 320


def lookUp(table, label, channel):
    name = label.split("/")[-1]
    for key in ((label, channel), (name, channel), (label, "*"), (name, "*"), ("*", channel)):
        if key in table:
            return table[key]
    return None


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int64)


def checkScan(entries, expected):
    problems = []
    if len(entries) != expected["sets"]:
        problems.append(f"found {len(entries)} texture sets, expected {expected['sets']}")
    incomplete = [entry.name for entry in entries if not entry.complete]
    if incomplete:
        problems.append(f"incomplete: {', '.join(incomplete)}")
    for label, found, wanted in (
        ("CC variants", {entry.name for entry in entries if entry.variantOf}, expected["variants"]),
        ("copied CC textures", {entry.name for entry in entries if entry.maskIsCopy}, expected["copies"]),
        ("names to check", {entry.name for entry in entries if entry.guessed}, expected["checkNames"]),
    ):
        if found != wanted:
            problems.append(f"{label} {sorted(found)}, expected {sorted(wanted)}")
    return problems


def checkTexture(job):
    """Returns (problems as (CC colour or "*", text), report text, thumbnails or None)."""
    entry, profile, finalPath, fromGrey, thumbnails = job
    base, grey, mask, final = load(entry.base), load(entry.grey), load(entry.mask), load(finalPath)
    if not (base.shape == grey.shape == mask.shape == final.shape):
        sizes = f"base {base.shape[1::-1]}, grey {grey.shape[1::-1]}, CC {mask.shape[1::-1]}, final {final.shape[1::-1]}"
        return [("*", f"sizes differ: {sizes}")], "", None
    rendered = ColourHandler.imageRecolour(base, grey, mask, profile).astype(np.int64)
    shown = rendered
    if not fromGrey:
        # The finals were painted evenly (no CC strength), so their colours are compared with an evenly painted render
        even = dataclasses.replace(profile, channels={channel: dataclasses.replace(spec, ccStrength=False)
                                                      for channel, spec in profile.channels.items()})
        rendered = ColourHandler.imageRecolour(base, grey, mask, even).astype(np.int64)
    problems = []
    labels = ColourHandler.classifyMask(mask)
    copy = ColourHandler.maskIsCopy(base, grey, mask)

    if fromGrey:
        # Every part is made from the grey texture, so every part is compared with the game texture
        changed = np.ones(labels.shape, dtype=bool)
        report = []
        limit = GAME_COLOUR_MAX
    else:
        changed = np.abs(final - base).sum(axis=-1) > 30
        limit = FLAT_COLOUR_MAX
        # Parts the final left alone: CC colours with (almost) no changed pixels. Pixels of a recoloured part that
        # happen to equal the base, like black paint on black, don't count.
        report = []
        unchanged = (final == base).all(axis=-1)
        for index, channel in enumerate(MASK_CHANNELS):
            part = labels == index
            if not part.any() or not (copy or changed[part].mean() < 0.02):
                continue
            kept = part & unchanged
            if kept.sum() >= MIN_PART_PIXELS:
                identical = ((rendered == base).all(axis=-1) & kept).sum() / kept.sum() * 100
                report.append(f"{channel} kept {identical:.1f}%")
                if identical < KEPT_IDENTICAL_MIN:
                    problems.append((channel, f"only {identical:.2f}% of the {channel} part the final kept is unchanged"))

    if not copy:
        for index, channel in enumerate(MASK_CHANNELS):
            part = (labels == index) & changed
            if part.sum() < MIN_PART_PIXELS:
                continue
            ours, theirs = np.median(rendered[part], axis=0), np.median(final[part], axis=0)
            difference = np.abs(ours - theirs).max()
            mae = np.abs(rendered[part] - final[part]).mean()
            report.append(f"{channel}: {theirs.astype(int).tolist()} -> {ours.astype(int).tolist()} (off {difference:.0f}, MAE {mae:4.1f})")
            if difference > limit:
                problems.append((channel, f"{channel} part's colour is off by {difference:.0f}"))

    pictures = None
    if thumbnails:
        pictures = [np.asarray(Image.fromarray(image.astype(np.uint8)).resize((SHEET_SIZE, SHEET_SIZE))) for image in (base, final, shown)]
    return problems, " | ".join(report), pictures


def writeSheet(rows, path):
    size = SHEET_SIZE
    sheet = Image.new("RGB", (3 * size, len(rows) * (size + 20)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (name, pictures) in enumerate(rows):
        for column, (label, image) in enumerate(zip(("base", "final", "this app"), pictures)):
            sheet.paste(Image.fromarray(image), (column * size, row * (size + 20) + 20))
            draw.text((column * size + 4, row * (size + 20) + 4), f"{name}: {label}", fill="black")
    sheet.save(path)


def uniformEntries(uniform, teamFolder, example):
    """
    The texture sets of one team's uniform in Uniforms. Later folders replace files of the same name from earlier ones:
    base textures are the Ultramarine game textures, then Shared, then the team's own; grey and CC textures Shared, then the team's.
    """
    def files(*folders):
        found = {}
        for folder in folders:
            found.update({path.name.lower(): path for path in FileHandler.findImages(folder)} if folder.is_dir() else {})
        return list(found.values())

    gameTextures = UNIFORMS / "Ultramarines" / uniform / "Final" if uniform in GAME_UNIFORMS else SHARED / uniform / "Base"
    fallback = example.get("ccFallback")
    masks = files(*([fallback / uniform / "CC"] if fallback else []), SHARED / uniform / "CC", teamFolder / "CC")
    for path, team in example.get("ccFallbackFiles", {}).items():
        if path.startswith(uniform + "/"):
            masks = [mask for mask in masks if mask.name != Path(path).name] + [team / uniform / "CC" / Path(path).name]
    return FileHandler.scanTextureFiles(files(gameTextures, SHARED / uniform / "Base", teamFolder / "Base"),
                                        files(SHARED / uniform / "A", teamFolder / "A"), masks)


def checkExample(name, example, profiles, pool, rows, thumbnails, counts, textures):
    """Prints the results for one example and returns the number of failed checks."""
    folder = example["folder"]
    print(f"\n== {name}: {folder}")
    if not folder.is_dir():
        print("SKIP folder not found")
        return 0

    failures = 0
    jobs = []
    for uniform in example.get("uniforms", (None,)):
        uniformFolder = folder / uniform if uniform else folder
        if not uniformFolder.is_dir():
            print(f"SKIP {uniform}: folder not found")
            continue
        entries = uniformEntries(uniform, uniformFolder, example) if uniform else FileHandler.scanTextureFolders(uniformFolder)
        if "scan" in example:
            problems = checkScan(entries, example["scan"])
            print(("FAIL" if problems else "PASS") + " scan: " + ("; ".join(problems) if problems else f"{len(entries)} texture sets as expected"))
            failures += bool(problems)
        for entry in entries:
            label = f"{uniform}/{entry.name}" if uniform else entry.name
            if textures and not any(fnmatch.fnmatch(text.lower(), pattern.lower()) for pattern in textures for text in (label, entry.name)):
                continue
            finalName = example.get("finalNames", {}).get(label, example.get("finalNames", {}).get(entry.name, entry.name))
            finalPath = uniformFolder / "Final" / (finalName + ".png")
            if not finalPath.exists():
                continue
            if not entry.complete:
                print(f"SKIP {label:34s} incomplete texture set")
                continue
            if entry.name in SKIPPED:
                print(f"SKIP {label:34s} {SKIPPED[entry.name]}")
                continue
            chosen = example["profiles"]
            profileName = chosen.get(label, chosen.get(entry.variantOf or entry.name, example["default"]))
            jobs.append((label, profileName, (entry, profiles[profileName], finalPath, example.get("fromGrey", False), thumbnails)))

    notes, openQuestions = NOTES.get(example.get("notes"), {}), OPEN.get(example.get("notes"), {})
    for (label, profileName, _job), (problems, report, pictures) in zip(jobs, pool.map(checkTexture, [job for *_rest, job in jobs])):
        verdicts = {"FAIL": [], "OPEN": [], "NOTE": []}
        for channel, text in problems:
            if lookUp(notes, label, channel):
                verdicts["NOTE"].append(f"{text}: {lookUp(notes, label, channel)}")
            elif lookUp(openQuestions, label, channel):
                verdicts["OPEN"].append(f"{text}: {lookUp(openQuestions, label, channel)}")
            else:
                verdicts["FAIL"].append(text)
        verdict = "FAIL" if verdicts["FAIL"] else "OPEN" if verdicts["OPEN"] else "PASS"
        failures += verdict == "FAIL"
        counts[verdict] += 1
        print(f"{verdict} {label:34s} {profileName:28s} {report or 'no parts compared'}")
        for kind in ("FAIL", "OPEN", "NOTE"):
            for text in verdicts[kind]:
                print(f"       {kind}: {text}")
        if pictures:
            rows.append((label, pictures))
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--only", choices=sorted(EXAMPLES), help="check only this example")
    parser.add_argument("--texture", action="append", help="check only textures matching this name or uniform/name (* allowed); repeatable")
    parser.add_argument("--sheet", type=Path, help="also save a base / final / this app comparison image here")
    parser.add_argument("--profiles", type=Path, default=FileHandler.PROFILES_FILE, help="profile file (default: profiles.toml)")
    args = parser.parse_args()

    profiles = loadProfiles(args.profiles)
    rows = []
    counts = {"PASS": 0, "OPEN": 0, "FAIL": 0}
    with ProcessPoolExecutor(max(1, min(8, (os.cpu_count() or 2) - 1))) as pool:
        failures = sum(checkExample(name, example, profiles, pool, rows, bool(args.sheet), counts, args.texture)
                       for name, example in EXAMPLES.items() if args.only in (None, name))

    if args.sheet:
        writeSheet(rows, args.sheet)
        print(f"\nComparison saved to {args.sheet}")
    print(f"\n{counts['PASS']} passed, {counts['OPEN']} open (listed above, they need a decision), {counts['FAIL']} failed.")
    print("All checks passed." if not failures else f"{failures} check(s) failed.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
