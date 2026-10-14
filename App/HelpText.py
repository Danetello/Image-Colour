"""
Help topics shown in the help window, in the order a new user meets things.

Markup: "## " starts a heading, "- " a bullet, "1. " a numbered step, **text** is bold (the lead of an item,
or a control name exactly as the screen shows it), *text* is italic (an aside or a reference to another topic)
and `text` is literal (file and folder names).
Blank lines separate paragraphs. Run this file to check the markup.
"""
import re

TOPICS = [
    ("getting-started", "Getting started", """
This app recolours Space Marine 2 armour textures. You choose the new colours once and save them as a **profile**. Then you can recolour as many textures as you like with that profile.

## What you need
Each texture comes as three image files, together called a **texture set**:
- **Base texture**: the original coloured texture, in the `Base` folder.
- **Grey texture**: the same texture in shades of grey, with `_a` at the end of its name, in the `Grey` folder.
- **CC texture**: a map in red, green and blue that marks the parts to recolour, with `_cc` at the end of its name, in the `CC` folder.

These three folders are in `Textures`, next to `run.bat`. The app makes them, with a short guide, when they're missing.

For example: `Snow_Shoulder_R.png`, `Snow_Shoulder_R_a.png` and `Snow_Shoulder_R_cc.png`.

## Make a profile
Skip this if one of the ready-made profiles already has the colours you want.
1. Open the **Profile editor** tab and choose a **Texture set**.
2. For each part you want to change, set **Action** to **Recolour** and pick a **New colour**.
3. Press **Render** to see the result. Change the colours and render again until you're happy.
4. Type a **Name** and press **Save profile**.

## Recolour your textures
1. On the **Batch** tab, select texture sets in **Texture sets found** and press **Add selected to batch**.
2. Choose a **Profile** under the batch and press **Use for all**. Parts that need other colours, like shoulder pads, can have their own profile.
3. Press **Render**, then **Open output folder** to see the results.

Each run is saved in new folders inside `Output`, one per profile, named after the profile and the time, so earlier results are never overwritten.

## Help is always nearby
The bar at the top of each tab always says what to do next. Press **?** next to a section for help on it, or **Help** at the top of the window for every topic.
"""),

    ("texture-sets", "Texture sets and CC colours", """
## CC colours
Every pixel of the CC texture is red, green, blue, pure white or pure black. These five colours are the **CC colours**. Each one marks a part of the armour, and a profile says what happens to each part:
- **Keep original** copies that part from the base texture unchanged.
- **Recolour** paints that part in the new colour and keeps its scratches and grime.
- **Use grey texture** copies that part from the grey texture.

**What each CC colour covers differs between textures.** Red is usually the main armour and green the chapter symbol, but check it: in the **Profile editor**, press **Show** next to a CC colour to highlight its part of the texture.

## How files are matched
Files are matched by name: `Name.png` in `Base`, `Name_a.png` in `Grey` and `Name_cc.png` in `CC`. Upper and lower case don't matter. The folders can also be called `A` (grey) and `Mask` (CC), or `Textures_Base`, `Textures_Grey` and `Textures_Mask`. To use textures from somewhere else, press **Select folder…** on the **Batch** tab and choose the folder that holds these three.

An extra CC texture named after a base texture plus more, such as `Pilot_Helmet_checker_cc.png` next to `Pilot_Helmet.png`, becomes its own texture set that uses that base and grey texture. Use this for alternative decals; the result is named after the CC texture, for example `Pilot_Helmet_checker.png`.

## Statuses in Texture sets found
- **✓ Ready**: all three files were found and are the same size. *Extra CC for …* marks an extra CC texture for another texture set.
- **⚠ CC is a copy: saved unchanged**: the CC file is a copy of the base or grey texture, so it marks no parts. Rendering saves the base texture unchanged.
- **⚠ Check names**: the names only roughly match, for example `Shoulder_Left` and `Shoulder_Lft`. Compare the three names in the row. If they belong together, render it as it is. If not, fix it with **Change files…**.
- **✕ Missing … texture**: a file wasn't found. Put it in its folder and press **Rescan**, or pick it with **Change files…**.
- **✕ Sizes differ**: the three files aren't the same size, so they can't be combined. Pick matching files with **Change files…**.
- **✕ Can't read a file**: a file is damaged or isn't an image.

**Change files…** only lasts until the next **Rescan**. To fix a texture set for good, rename its files.
"""),

    ("batch", "Rendering a batch", """
## Render textures
1. Select texture sets in **Texture sets found**. Hold Ctrl to select several, or Shift to select a range. Double-click a row to add only that one.
2. Press **Add selected to batch**. Texture sets marked ✕ can't be added; the message next to the buttons says why.
3. Choose a **Profile** under the batch and press **Use for all**. Texture sets you add later get the chosen profile straight away.
4. Press **Render all**. To render only part of the batch, select those rows first; the button then says **Render** and the number selected.

## Different profiles in one batch
Parts of one armour set often need different colours, for example green armour with black shoulder pads. Select those texture sets in the batch, choose their **Profile** and press **Use for**; the button says how many are selected. The **Profile** column shows what each texture set gets.

The ready-made profiles come in families for this: the main profile, such as `salamanders`, then `_black` for black parts such as shoulder pads, `_gold_trim` where the base texture has no gold yet, and `_grey_trim` where trims stay as in the grey texture. **Profiles marked (experimental) haven't been checked against finished textures yet.**

## While it renders
- Each row shows **Waiting**, **Rendering…**, **Done**, or **Failed** with the reason.
- **Stop batch** lets the textures already rendering finish and skips the rest.
- **You can't close the app while a batch is rendering.** Press **Stop batch** first.
- You can keep working in the **Profile editor** meanwhile.

## Threads
**Threads** is how many textures render at the same time. It starts at the number of threads your processor has, which is the fastest. Lower it to keep the computer responsive for other work. If the app couldn't detect your processor, it says so next to the box: choose a number yourself, 4 is a safe start.

## Where the results go
Every run makes a new folder in `Output` for each profile it uses, named after the profile and the start time, for example `Output/salamanders_2026-10-14_21-30-05`. Batches always render at full resolution. Each result keeps the name of its base texture, or of its CC texture for an extra CC. Press **Open output folder** to open the folder of the latest run, or `Output` when the run used several profiles. Results keep the transparency of their base texture.
"""),

    ("editor", "Making a profile", """
## 1. Choose a texture set
Pick one in **Texture set**, or press **Choose files…** to use any three files. Choose a texture that shows all the parts you want to recolour. Its base, grey and CC textures appear on the left; switch between them with the buttons above the picture.

## 2. Set the colours
For each CC colour:
- **Area** says how much of this texture it covers. **Not used here** means this texture doesn't contain that CC colour, but other textures may.
- Press **Show** to highlight that part of the texture.
- Set **Action** to **Recolour** and pick a **New colour**: click the colour box to open a colour picker, or type a colour code such as `#2f5d2a`.

**New colour is exactly what clean, undamaged paint will look like.** Scratches and grime are added on top automatically. A recoloured part starts with the colour of the original texture, so you can see what changes.

## 3. Render
Press **Render** or F5. The result appears on the right in under a second. It's a half-size preview, which is quicker. Zooming in past 50% renders every pixel by itself; switch on **Full resolution** to always render every pixel. Batches always render at full resolution. After you change a setting, the line next to **Render** says the result is out of date until you render again. Switch on **Render automatically** to update the result after every change.

## 4. Save
Type a **Name** using letters, digits, `_` and `-`, and optionally a **Description**. Then press **Save profile**. The profile is immediately available in the **Profile** list on the **Batch** tab.

## Change an existing profile
Choose it in **Profile** to load its settings. Saving under the same name replaces it, and keeps its (experimental) mark if it has one; saving under a new name makes a copy. **New profile** starts again with every CC colour set to **Keep original**.
"""),

    ("fine-tuning", "Fine-tuning", """
Switch on **Fine-tuning** to show four more settings for each recoloured CC colour. At 1 the first three match the original game textures, and most profiles never need to change them.
- **Detail**: how strongly scratches and grime show. Lower it for cleaner, flatter paint; 0 gives a flat colour.
- **Highlights**: how far scratches and worn edges can lighten the colour. Raise it to make wear stand out on dark colours. Metal such as gold or silver needs about 3.
- **Shadows**: how far grime and crevices can darken the colour. Raise it for a dirtier look on light colours.
- **CC strength**: on, the default, the part gets less paint where its CC colour is faint, as in the game, so worn edges show the grey texture. Off paints the whole part evenly.

Detail, Highlights and Shadows accept values from 0 to 3. Shading only goes as far as a colour has room for before it reaches black or white, so very dark and very light colours keep their detail.
"""),

    ("views", "Zooming and comparing", """
- **Scroll** over a picture to zoom in or out at the pointer.
- **Drag** to move around.
- **Double-click** to go back to actual size.

The pictures never shrink below actual size, so you always see every pixel: one screen pixel per texture pixel with **Full resolution** on, and one per preview pixel with it off. Zooming in goes in whole steps (2×, 3×, 4×…), so pixels stay sharp.

Both pictures always show the same part of the texture, so you can compare the original with the result.
"""),

    ("troubleshooting", "Troubleshooting", """
- **No texture sets found.** Put the files in `Base`, `Grey` and `CC` inside the texture folder shown at the top of the **Batch** tab (normally `Textures`), then press **Rescan**. **Select folder…** scans another folder.
- **A texture set shows ⚠ or ✕.** See the statuses under *Texture sets and CC colours*.
- **One part needs a different colour from the rest, like shoulder pads.** Make a profile for that part, then give it to just those texture sets on the **Batch** tab: select them, choose the **Profile** and press **Use for**.
- **The wrong part changed colour.** CC colours mark different parts on different textures. Press **Show** in the **Profile editor** to see which part each one covers, and set its **Action** to match.
- **The colour looks too dark or too light.** **New colour** is the colour of clean paint. Pick a lighter or darker one; the scratches stay.
- **Scratches are too strong or too faint.** Switch on **Fine-tuning** and change **Detail**, **Highlights** or **Shadows**.
- **A row says Failed.** The reason follows the word Failed. Usually a file is damaged or was moved during the render. Fix it and render again.
- **The app doesn't start.** Run `App\\install_venv.bat` on Windows or `App/install_venv.sh` on Linux and macOS, and read its messages. You need Python 3.12 or newer.
"""),
]

TOPIC_TITLES = {key: title for key, title, _body in TOPICS}


def topicBody(key):
    return next(body for topicKey, _title, body in TOPICS if topicKey == key).strip()


def markupProblems():
    """Lists malformed markup, so it's caught before it reaches the screen."""
    problems = []
    for key, _title, body in TOPICS:
        for number, line in enumerate(body.strip().splitlines(), start=1):
            if line.count("**") % 2:
                problems.append(f"{key} line {number}: unpaired ** in: {line.strip()[:60]}")
            elif line.replace("**", "").count("*") % 2:
                problems.append(f"{key} line {number}: unpaired * in: {line.strip()[:60]}")
            if line.count("`") % 2:
                problems.append(f"{key} line {number}: unpaired ` in: {line.strip()[:60]}")
            if re.match(r"^\s*#(?!# )", line) or line.startswith("### "):
                problems.append(f"{key} line {number}: only '## ' headings are supported")
    return problems


if __name__ == "__main__":
    found = markupProblems()
    print("\n".join(found) if found else f"{len(TOPICS)} help topics, markup OK")
    raise SystemExit(1 if found else 0)
