"""
Checks the app against the hand-made example sets: every texture set is rendered with its profile and compared
with the matching image in the example's Final folder.

Run from the project folder:  python tests/check_dev_example.py [--only salamanders] [--sheet comparison.png]
Exit code 0 means every check passed.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import ColourHandler  # noqa: E402
import FileHandler  # noqa: E402
from ProfileHandler import MASK_CHANNELS, loadProfiles  # noqa: E402

EXAMPLES = {
    "salamanders": {
        "folder": PROJECT_DIR / "Dev Example",
        "default": "salamanders",
        "profiles": {
            "Pilot_Helmet": "salamanders_helmet",
            "Pilot_Shoulder_L": "salamanders_shoulders",
            "Pilot_Shoulder_R": "salamanders_shoulders",
        },
        "sets": 18,
        "variants": {"Pilot_Helmet_checker", "Pilot_Helmet_line", "Pilot_Helmet_mask", "Pilot_Helmet_mask2", "Pilot_Helmet_mohawk"},
        "copies": {"Pilot_Arm", "Pilot_Vanity_4"},
        "checkNames": {"Pilot_Arm"},
    },
    "templars": {
        "folder": PROJECT_DIR / "Dev Example Soldier Templar" / "Soldier",
        "default": "black_templars",
        "profiles": {
            "Soldier_Shoulders": "black_templars_shoulders",
            "Soldier_Boots": "black_templars_all_black",
            "Soldier_Trims": "black_templars_all_black",
        },
        "sets": 15,
        "variants": set(),
        "copies": set(),
        # These base files are named like grey textures (Soldier_Backpack_a.png)
        "checkNames": {"Soldier_Backpack", "Soldier_Boots", "Soldier_Helmet", "Soldier_Shin", "Soldier_Side_Plate"},
    },
}

# Differences from the finals that are intended. The old formula made paint darker wherever the grey texture is
# lighter; the app gives a part exactly its profile's colour, so the same paint matches on every part.
KNOWN_DIFFERENCES = {
    ("Pilot_Vanity_1", "red"): "the final's green is darker here because the old formula darkened lighter grey; the app keeps one green",
    ("Soldier_Backpack", "blue"): "the final's silver is lighter on this tiny part because the old formula lightened darker grey; "
                                  "the app keeps one silver",
}

# Pass limits
KEPT_IDENTICAL_MIN = 99.5  # % of the pixels the final left unchanged that must be unchanged here too
FLAT_COLOUR_MAX = 6  # largest allowed difference per channel between the median colours of a changed part


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int64)


def checkScan(entries, example):
    problems = []
    if len(entries) != example["sets"]:
        problems.append(f"found {len(entries)} texture sets, expected {example['sets']}")
    incomplete = [entry.name for entry in entries if not entry.complete]
    if incomplete:
        problems.append(f"incomplete: {', '.join(incomplete)}")
    for label, found, expected in (
        ("CC variants", {entry.name for entry in entries if entry.variantOf}, example["variants"]),
        ("copied CC textures", {entry.name for entry in entries if entry.maskIsCopy}, example["copies"]),
        ("names to check", {entry.name for entry in entries if entry.guessed}, example["checkNames"]),
    ):
        if found != expected:
            problems.append(f"{label} {sorted(found)}, expected {sorted(expected)}")
    return problems


def checkTexture(entry, profile, final):
    """Returns (problems, report text, rendered image)."""
    base, grey, mask = load(entry.base), load(entry.grey), load(entry.mask)
    rendered = ColourHandler.imageRecolour(base, grey, mask, profile).astype(np.int64)
    problems = []
    labels = ColourHandler.classifyMask(mask)
    changed = np.abs(final - base).sum(axis=-1) > 30

    # Parts the final left alone: CC colours with (almost) no changed pixels. Pixels of a recoloured part that
    # happen to equal the base, like black paint on black, don't count.
    keptParts = np.zeros(labels.shape, dtype=bool)
    for index in range(len(MASK_CHANNELS)):
        part = labels == index
        if part.any() and changed[part].mean() < 0.02:
            keptParts |= part
    if ColourHandler.maskIsCopy(base, grey, mask):
        keptParts[:] = True
    kept = keptParts & (final == base).all(axis=-1)
    if kept.any():
        identical = ((rendered == base).all(axis=-1) & kept).sum() / kept.sum() * 100
        report = [f"kept parts identical {identical:6.2f}%"]
        if identical < KEPT_IDENTICAL_MIN:
            problems.append(f"only {identical:.2f}% of the parts the final kept are unchanged")
    else:
        report = ["no kept parts"]

    if not ColourHandler.maskIsCopy(base, grey, mask):
        for index, channel in enumerate(MASK_CHANNELS):
            part = (labels == index) & changed
            if part.sum() < 1000:
                continue
            ours, theirs = np.median(rendered[part], axis=0), np.median(final[part], axis=0)
            difference = np.abs(ours - theirs).max()
            mae = np.abs(rendered[part] - final[part]).mean()
            report.append(f"{channel}: {theirs.astype(int).tolist()} -> {ours.astype(int).tolist()} (off {difference:.0f}, MAE {mae:4.1f})")
            if difference > FLAT_COLOUR_MAX:
                known = KNOWN_DIFFERENCES.get((entry.name, channel))
                if known:
                    report.append(f"NOTE: {known}")
                else:
                    problems.append(f"{channel} part's colour is off by {difference:.0f}")
    return problems, " | ".join(report), rendered


def writeSheet(rows, path, size=320):
    sheet = Image.new("RGB", (3 * size, len(rows) * (size + 20)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (name, base, final, rendered) in enumerate(rows):
        for column, (label, image) in enumerate((("base", base), ("final", final), ("this app", rendered))):
            sheet.paste(Image.fromarray(image.astype(np.uint8)).resize((size, size)), (column * size, row * (size + 20) + 20))
            draw.text((column * size + 4, row * (size + 20) + 4), f"{name}: {label}", fill="black")
    sheet.save(path)


def checkExample(name, example, profiles, rows):
    """Prints the results for one example and returns the number of failed checks."""
    print(f"\n== {name}: {example['folder'].relative_to(PROJECT_DIR)}")
    if not example["folder"].is_dir():
        print("FAIL folder not found")
        return 1
    entries = FileHandler.scanTextureFolders(example["folder"])
    problems = checkScan(entries, example)
    print(("FAIL" if problems else "PASS") + " scan: " + ("; ".join(problems) if problems else f"{len(entries)} texture sets as expected"))
    failures = int(bool(problems))

    for entry in entries:
        finalPath = example["folder"] / "Final" / (entry.name + ".png")
        if not entry.complete or not finalPath.exists():
            continue
        profileName = example["profiles"].get(entry.variantOf or entry.name, example["default"])
        final = load(finalPath)
        problems, report, rendered = checkTexture(entry, profiles[profileName], final)
        failures += bool(problems)
        print(f"{'FAIL' if problems else 'PASS'} {entry.name:24s} {profileName:26s} {report}" + (f"  <- {'; '.join(problems)}" if problems else ""))
        rows.append((entry.name, load(entry.base), final, rendered))
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--only", choices=sorted(EXAMPLES), help="check only this example")
    parser.add_argument("--sheet", type=Path, help="also save a base / final / this app comparison image here")
    args = parser.parse_args()

    profiles = loadProfiles(PROJECT_DIR / "profiles.toml")
    rows = []
    failures = sum(checkExample(name, example, profiles, rows) for name, example in EXAMPLES.items() if args.only in (None, name))

    if args.sheet:
        writeSheet(rows, args.sheet)
        print(f"\nComparison saved to {args.sheet}")
    print(f"\n{'All checks passed' if not failures else f'{failures} check(s) failed'}.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
