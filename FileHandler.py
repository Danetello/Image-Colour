import difflib
import filecmp
import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

BASE_FOLDER = "Textures_Base"
GREY_FOLDER = "Textures_Grey"
MASK_FOLDER = "Textures_Mask"
OUTPUT_FOLDER = "output"

# Other folder names that are recognised, in order of preference after the standard name
FOLDER_ALIASES = {
    BASE_FOLDER: ["Base"],
    GREY_FOLDER: ["Grey", "A"],
    MASK_FOLDER: ["Mask", "CC"],
}

# Expected file name suffixes, e.g. Foo.png -> Foo_a.png (grey) and Foo_cc.png (CC)
GREY_SUFFIX = "_a"
MASK_SUFFIX = "_cc"

IMAGE_EXTENSIONS = {".png", ".tga", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# How alike two names must be (0-1) to be paired as a guess
GUESS_CUTOFF = 0.75


@dataclass(frozen=True)
class TextureSet:
    name: str
    base: Path
    grey: Path
    mask: Path


@dataclass
class TextureEntry:
    """A base, grey and CC texture that belong together. Any of them can be missing."""
    name: str
    base: Path = None
    grey: Path = None
    mask: Path = None
    guessed: bool = False  # paired by similar rather than matching names
    variantOf: str = None  # name of the texture set whose base and grey this extra CC texture uses
    maskIsCopy: bool = False  # the CC file is the base or grey file, so there's nothing to recolour

    @property
    def complete(self):
        return self.base is not None and self.grey is not None and self.mask is not None

    def textureSet(self):
        return TextureSet(self.name, self.base, self.grey, self.mask)


def outputFolderName(profileName, when):
    return f"{profileName}_{when:%Y-%m-%d_%H-%M-%S}"


def textureFolder(root, standardName):
    """The standard folder if it exists, otherwise the first alias that does (e.g. Base, A, CC)."""
    for name in [standardName] + FOLDER_ALIASES[standardName]:
        if (Path(root) / name).is_dir():
            return Path(root) / name
    return Path(root) / standardName


def findImages(folder):
    """Returns every image in the folder and its subfolders, sorted by path."""
    return [
        path
        for path in sorted(Path(folder).rglob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def pairKey(path, suffix=""):
    """Name used for pairing: lower case, texture suffix removed, letters and digits only."""
    stem = path.stem.lower()
    if suffix:
        stem = re.sub(rf"[_\-. ]{re.escape(suffix.lstrip('_'))}$", "", stem)
    return re.sub(r"[^a-z0-9]", "", stem)


def matchFiles(keys, candidates, exact):
    """
    Pairs each key with one candidate {key: path}, removing matched candidates.
    exact=False pairs remaining keys with the most similar remaining candidate name.
    """
    matches = {}
    for key in keys:
        if exact:
            found = key if key in candidates else None
        else:
            close = difflib.get_close_matches(key, list(candidates), n=1, cutoff=GUESS_CUTOFF)
            found = close[0] if close else None
        if found is not None:
            matches[key] = candidates.pop(found)
    return matches


def scanTextureFolders(root):
    """
    Groups the files in the three texture folders into TextureEntries.
    Exact name matches are paired first; leftovers are paired by similar names and marked as guessed.
    An extra CC texture named after a base texture plus more (Helmet_checker_cc.png next to Helmet.png)
    becomes a variant that uses that base and grey texture. Files that still have no partner become incomplete entries.
    """
    root = Path(root)
    bases = {}
    entries = {}
    misnamed = []
    for path in findImages(textureFolder(root, BASE_FOLDER)):
        bases[pairKey(path)] = path
    # A base texture named like a grey or CC texture (Foo_a.png) is paired and named as Foo, but flagged to check
    for key, path in list(bases.items()):
        for suffix in (GREY_SUFFIX, MASK_SUFFIX):
            stripped = pairKey(path, suffix)
            if stripped != key and stripped not in bases:
                bases[stripped] = bases.pop(key)
                misnamed.append(stripped)
                break
    greys = {pairKey(path, GREY_SUFFIX): path for path in findImages(textureFolder(root, GREY_FOLDER))}
    masks = {pairKey(path, MASK_SUFFIX): path for path in findImages(textureFolder(root, MASK_FOLDER))}

    for key, path in bases.items():
        name = path.stem
        if key in misnamed:
            name = next(stripSuffix(path, suffix) for suffix in (GREY_SUFFIX, MASK_SUFFIX) if pairKey(path, suffix) == key)
        entries[key] = TextureEntry(name, base=path, guessed=key in misnamed)

    for exact in (True, False):
        for attribute, candidates in (("grey", greys), ("mask", masks)):
            waiting = [key for key, entry in entries.items() if getattr(entry, attribute) is None]
            for key, path in matchFiles(waiting, candidates, exact).items():
                setattr(entries[key], attribute, path)
                entries[key].guessed |= not exact

    # Extra CC textures for a base texture, e.g. alternative decals
    for maskKey in list(masks):
        owners = [key for key in bases if maskKey.startswith(key) and maskKey != key and entries[key].grey is not None]
        if owners:
            owner = entries[max(owners, key=len)]
            path = masks.pop(maskKey)
            entries["variant:" + maskKey] = TextureEntry(stripSuffix(path, MASK_SUFFIX), base=owner.base, grey=owner.grey, mask=path,
                                                         guessed=owner.guessed, variantOf=owner.name)

    # Grey and CC textures without a base texture
    for exact in (True, False):
        for key, path in matchFiles(list(greys), masks, exact).items():
            entries["grey:" + key] = TextureEntry(stripSuffix(path, GREY_SUFFIX), grey=greys.pop(key), mask=path, guessed=not exact)
    for key, path in greys.items():
        entries["grey:" + key] = TextureEntry(stripSuffix(path, GREY_SUFFIX), grey=path)
    for key, path in masks.items():
        entries["mask:" + key] = TextureEntry(stripSuffix(path, MASK_SUFFIX), mask=path)

    for entry in entries.values():
        if entry.complete:
            entry.maskIsCopy = isSameFile(entry.mask, entry.base) or isSameFile(entry.mask, entry.grey)

    return sorted(entries.values(), key=lambda entry: entry.name.lower())


def isSameFile(first, second):
    try:
        return first.stat().st_size == second.stat().st_size and filecmp.cmp(first, second, shallow=False)
    except OSError:
        return False


def stripSuffix(path, suffix):
    return path.stem[: -len(suffix)] if path.stem.lower().endswith(suffix) else path.stem


def findTextureSets(root, only=None):
    """
    Returns (complete TextureSets with matching names, warnings for everything skipped).
    Pairs with only similar names are skipped here; confirm them in the GUI or fix the names.
    """
    textureSets = []
    warnings = []

    for entry in scanTextureFolders(root):
        if only and not any(fnmatch.fnmatch(entry.name.lower(), pattern.lower()) for pattern in only):
            continue
        if not entry.complete:
            missing = [label for label, path in (("base", entry.base), ("grey", entry.grey), ("CC", entry.mask)) if path is None]
            warnings.append(f"Skipping {entry.name}: no {' or '.join(missing)} texture found")
        elif entry.maskIsCopy:
            warnings.append(f"Note: {entry.name}'s CC texture is a copy of its base or grey texture, so it's saved unchanged")
            textureSets.append(entry.textureSet())
        elif entry.guessed:
            names = ", ".join(path.name for path in (entry.base, entry.grey, entry.mask))
            warnings.append(f"Skipping {entry.name}: names only roughly match ({names}); fix the names or confirm them in the GUI")
        else:
            textureSets.append(entry.textureSet())

    return textureSets, warnings
