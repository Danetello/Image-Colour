import numpy as np
from PIL import Image

from ProfileHandler import MASK_CHANNELS

RESOLUTION = 10000

RED, GREEN, BLUE, WHITE, BLACK = range(len(MASK_CHANNELS))

# Shade method constants, fitted against the original Ultramarine textures: around the typical
# grey value, base lightness changes ~0.5x as fast as grey lightness and levels off at ~0.1.
DETAIL_SLOPE = 0.5
SHIFT_LIMIT = 0.1

# CC strength: the game paints less where a CC colour is faint (scratches, worn edges), letting the grey texture
# show through. Fitted against the original Ultramarine textures: full paint from this CC value up, and
# sqrt(value / CC_FULL_STRENGTH) below it.
CC_FULL_STRENGTH = 128

# OKLab matrices (Björn Ottosson)
LINEAR_TO_LMS = np.array([
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
])
LMS_TO_OKLAB = np.array([
    [0.2104542553, 0.7936177850, -0.0040720468],
    [1.9779984951, -2.4285922050, 0.4505937099],
    [0.0259040371, 0.7827717662, -0.8086757660],
])
LMS_TO_LINEAR = np.linalg.inv(LINEAR_TO_LMS)
OKLAB_TO_LMS = np.linalg.inv(LMS_TO_OKLAB)

# Shading depends only on each grey pixel's lightness, so it's worked out once for this many evenly spaced
# lightness levels and looked up per pixel. Neighbouring levels differ by far less than one 8-bit step.
LIGHTNESS_LEVELS = 4096


def srgbToLinear(c):
    c = np.asarray(c, dtype=np.float64) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# Exact sRGB -> linear values for every 8-bit channel value
SRGB_TO_LINEAR = srgbToLinear(np.arange(256))


def srgbToOklab(rgb):
    return np.cbrt(srgbToLinear(rgb) @ LINEAR_TO_LMS.T) @ LMS_TO_OKLAB.T


def greyLightness(grey):
    """OKLab lightness of an (N, 3) array of 0-255 pixels."""
    return np.cbrt(SRGB_TO_LINEAR[grey] @ LINEAR_TO_LMS.T) @ LMS_TO_OKLAB[0]


def oklabToLinear(lab):
    return ((lab @ OKLAB_TO_LMS.T) ** 3) @ LMS_TO_LINEAR.T


def oklabToSrgb(lab):
    """Converts OKLab to 0-255 sRGB, reducing chroma (not hue or lightness) for colours outside sRGB."""
    lab = lab.copy()
    linear = oklabToLinear(lab)
    outside = ((linear < 0) | (linear > 1)).any(axis=-1)

    if outside.any():
        lo = np.zeros(outside.sum())
        hi = np.ones(outside.sum())
        for _ in range(16):
            mid = (lo + hi) / 2
            test = oklabToLinear(lab[outside] * np.column_stack([np.ones_like(mid), mid, mid]))
            fits = ((test >= -1e-6) & (test <= 1 + 1e-6)).all(axis=-1)
            lo = np.where(fits, mid, lo)
            hi = np.where(fits, hi, mid)
        lab[outside, 1:] *= lo[:, None]
        linear[outside] = oklabToLinear(lab[outside])

    c = np.clip(linear, 0, 1)
    return np.round(255 * np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)).astype(np.int64)


def extractImage(pathName):
    """Loads an image as an (height, width, 3) int64 RGB array."""
    return np.asarray(Image.open(pathName).convert("RGB"), dtype=np.int64)


def extractAlpha(pathName):
    """The image's transparency as an (height, width) uint8 array, or None if it has none."""
    with Image.open(pathName) as image:
        if "A" not in image.getbands() and "transparency" not in image.info:
            return None
        return np.asarray(image.convert("RGBA").getchannel("A"))


def classifyMask(mask):
    """
    Labels each mask pixel by its dominant channel: pure black and pure white get their
    own labels, otherwise red wins ties over green, and green over blue.
    """
    r, g, b = mask[..., 0], mask[..., 1], mask[..., 2]
    total = mask.sum(axis=-1)

    labels = np.where((r >= g) & (r >= b), RED, np.where(g >= b, GREEN, BLUE))
    labels[total == 765] = WHITE
    labels[total == 0] = BLACK
    return labels


def tintPixels(grey, spec):
    """Recolours an (N, 3) array of grey texture pixels with a tint channel spec."""
    if spec.method == "legacy":
        return legacyTintPixels(grey, spec)
    return shadePixels(grey, spec)


def softLimit(x, slope, limit):
    """Rises with `slope` near zero and levels off smoothly at +/- limit."""
    if limit <= 0:
        return np.zeros_like(x)
    return limit * np.tanh(slope * x / limit)


def shadePixels(grey, spec, lightness=None, median=None):
    """
    Pixels at the region's typical grey value get exactly the spec colour. Lighter or darker grey
    shifts the lightness up or down (keeping hue and saturation), limited by how much room the
    colour has, so near-black and near-white colours keep their detail instead of clipping.
    `lightness` and `median` can be passed in when they're already known for these pixels.
    """
    if lightness is None:
        lightness = greyLightness(grey)
    if spec.reference is not None:
        reference = spec.reference
    else:
        reference = np.median(lightness) if median is None else median

    table = shadeLevels(np.linspace(0.0, 1.0, LIGHTNESS_LEVELS), reference, spec)
    index = np.rint(lightness * (LIGHTNESS_LEVELS - 1)).astype(np.intp)
    np.clip(index, 0, LIGHTNESS_LEVELS - 1, out=index)
    return table[index]


def shadeLevels(levels, reference, spec):
    """The shaded colour for each grey lightness in `levels`."""
    target = srgbToOklab(spec.colour)
    offset = levels - reference
    slope = DETAIL_SLOPE * spec.detail
    roomUp = min(SHIFT_LIMIT * spec.highlights, 1 - target[0])
    roomDown = min(SHIFT_LIMIT * spec.shadows, target[0])
    shift = np.where(offset >= 0, softLimit(offset, slope, roomUp), softLimit(offset, slope, roomDown))

    lab = np.tile(target, (len(levels), 1))
    lab[:, 0] += shift
    return oklabToSrgb(lab)


def legacyTintPixels(grey, spec):
    """
    The original recolour: colour * (1 - grey brightness), then flip / lift rules.
    The darker the grey pixel, the closer the result is to the spec colour.
    """
    colour = np.array(spec.colour, dtype=np.float64)
    brightness = (grey.sum(axis=-1) / 765) * RESOLUTION

    invertPercentage = (RESOLUTION - brightness) / RESOLUTION
    out = np.round(colour * invertPercentage[:, None])

    # Pixels that came out too dark are rescaled by brightness instead
    if spec.flipBelow:
        flip = out.sum(axis=-1) < spec.flipBelow
        percentage = brightness[flip] / RESOLUTION
        out[flip] = np.round(colour * percentage[:, None])

    out = out.astype(np.int64)

    if spec.lift:
        out = applyLift(out, spec.lift, spec.liftMode)

    return np.clip(out, 0, 255)


def applyLift(out, rules, mode):
    """
    Applies `(pixel + add) * multiply` to pixels whose r+g+b sum is below each rule's threshold.
    mode "first": only the first matching rule applies (thresholds checked against the original sum).
    mode "all":   every rule is checked in turn against the sum after the previous rules.
    """
    startSum = out.sum(axis=-1)
    unmatched = np.ones(len(out), dtype=bool)

    for rule in rules:
        if mode == "all":
            hit = out.sum(axis=-1) < rule.below
        else:
            hit = unmatched & (startSum < rule.below)
            unmatched &= ~hit

        lifted = (out[hit] + np.array(rule.add)) * rule.multiply
        out[hit] = np.round(lifted).astype(np.int64)

    return out


def regionStats(base, labels):
    """
    For each mask channel: (fraction of the image it covers, median base colour or None).
    The median base colour is a good starting colour, as it reproduces the original look.
    """
    stats = {}
    for index, channel in enumerate(MASK_CHANNELS):
        selected = labels == index
        coverage = selected.mean()
        colour = medianColour(base[selected]) if selected.any() else None
        stats[channel] = (coverage, colour)
    return stats


def medianColour(pixels):
    """Per-channel median of (N, 3) 0-255 pixels, counted with histograms (much faster than sorting)."""
    middle = (len(pixels) + 1) // 2
    return tuple(int(np.searchsorted(np.cumsum(np.bincount(pixels[:, c], minlength=256)), middle)) for c in range(3))


def paintStrength(maskPixels, index):
    """How much paint (0-1) each (N, 3) CC pixel of mask channel `index` gets. Pure white and black are always full."""
    if index >= WHITE:
        return np.ones(len(maskPixels))
    return np.sqrt(np.minimum(maskPixels[:, index] / CC_FULL_STRENGTH, 1.0))


def blendPaint(grey, painted, strength):
    """Mixes grey texture pixels with painted pixels, by strength (0 = grey texture, 1 = painted)."""
    return np.rint(grey + (painted - grey) * strength[:, None]).astype(np.int64)


def maskIsCopy(base, grey, mask):
    """A CC texture that is a copy of the base or grey texture marks no parts, so nothing should change."""
    return np.array_equal(mask, base) or np.array_equal(mask, grey)


def imageRecolour(base, grey, mask, profile, labels=None, cache=None):
    """
    Builds the recoloured image from the three source textures and a profile.
    `cache` is an optional dict kept per texture set, so repeated renders skip work that doesn't depend on the profile.
    """
    if maskIsCopy(base, grey, mask):
        return base.astype(np.uint8)
    if labels is None:
        labels = classifyMask(mask)
    output = base.astype(np.uint8)

    for index, channel in enumerate(MASK_CHANNELS):
        spec = profile.channels[channel]
        if spec.style == "keep":
            continue

        selected = labels == index
        if not selected.any():
            continue

        if spec.style == "grey":
            output[selected] = grey[selected]
            continue
        if spec.method == "shade" and cache is not None:
            if index not in cache:
                lightness = greyLightness(grey[selected])
                cache[index] = (lightness, np.median(lightness))
            lightness, median = cache[index]
            painted = shadePixels(None, spec, lightness, median)
        else:
            painted = tintPixels(grey[selected], spec)
        if spec.method == "shade" and spec.ccStrength:
            if cache is not None:
                if ("strength", index) not in cache:
                    cache[("strength", index)] = paintStrength(mask[selected], index)
                strength = cache[("strength", index)]
            else:
                strength = paintStrength(mask[selected], index)
            if strength.min() < 1:
                painted = blendPaint(grey[selected], painted, strength)
        output[selected] = painted

    return output


def createRecolour(job):
    """
    Worker entry point. `job` is (textureSet, profile, outputDir).
    Returns (outputPath, None, note) on success, where note is None or something the user should know,
    or (textureName, errorMessage, None) on failure.
    """
    textureSet, profile, outputDir = job
    try:
        base = extractImage(textureSet.base)
        grey = extractImage(textureSet.grey)
        mask = extractImage(textureSet.mask)

        if not (base.shape == grey.shape == mask.shape):
            raise ValueError(f"size mismatch: base {base.shape[1::-1]}, grey {grey.shape[1::-1]}, mask {mask.shape[1::-1]}")

        note = "CC texture is a copy of the base, so it was saved unchanged" if maskIsCopy(base, grey, mask) else None
        newImage = imageRecolour(base, grey, mask, profile)
        # Keep the base texture's transparency, such as cut-out edges
        alpha = extractAlpha(textureSet.base)
        if alpha is not None:
            newImage = np.dstack([newImage, alpha])

        outputDir.mkdir(parents=True, exist_ok=True)
        outputPath = outputDir / (textureSet.name + ".png")
        Image.fromarray(newImage).save(outputPath)
        return outputPath, None, note

    except Exception as e:
        return textureSet.name, f"{type(e).__name__}: {e}", None
