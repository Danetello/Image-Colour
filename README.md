# Foxhole: Space Marine 2 Image Colouring Tool

Recolours the Space Marine 2 uniform textures for the Foxhole: Space Marine Uniform Mod.

Build a profile visually, then render whole batches of textures with it.

## What's where

| Folder or file  | What it holds                                                               |
|-----------------|-----------------------------------------------------------------------------|
| `run.bat`       | Starts the app on Windows (`./run.sh` on Linux and macOS)                   |
| `Textures`      | Your textures to recolour, in `Base`, `Grey` and `CC`                       |
| `Output`        | The results, one folder per profile and run                                 |
| `profiles.toml` | The profiles: the colours for each team and part                            |
| `Examples`      | Finished armour sets to compare with                                        |
| `App`           | The program itself, its setup scripts and tests. You don't need to open it. |

The app makes `Textures` (with a short guide, `How to use this folder.txt`) and `Output` when they're
missing.

## Setup and running

Requires **Python 3.12 or newer** (checked by the scripts and at startup).

| Windows                | Linux / macOS           | What it does                                                         |
|------------------------|-------------------------|----------------------------------------------------------------------|
| `run.bat`              | `./run.sh`              | Starts the app. Sets up the virtual environment first when needed.   |
| `App\install_venv.bat` | `./App/install_venv.sh` | Creates or updates the virtual environment in `App/venv` on its own. |

`run` sets up the environment automatically when it's missing or `App/requirements.txt` has changed.
On Linux the GUI needs tkinter, e.g. `sudo apt install python3-tk`.

## Textures

Each texture set is three files in the `Textures` folder, matched by name:

| Folder           | Contents                           | Example                  |
|------------------|------------------------------------|--------------------------|
| `Textures/Base`  | the original (Ultramarine) texture | `Snow_Shoulder_R.png`    |
| `Textures/Grey`  | the grey texture, suffix `_a`      | `Snow_Shoulder_R_a.png`  |
| `Textures/CC`    | the CC texture, suffix `_cc`       | `Snow_Shoulder_R_cc.png` |

To use textures somewhere else, press **Select folder…** on the **Batch** tab and choose the folder that holds
`Base`, `Grey` and `CC`. Those folders can also be called `A` (grey) and `Mask` (CC), or have the older names
`Textures_Base`, `Textures_Grey` and `Textures_Mask`. An extra CC texture such as `Pilot_Helmet_checker_cc.png`
next to `Pilot_Helmet.png` becomes its own texture set (alternative decals), and a CC file that is a copy of the
base texture is recognised and saved unchanged.

Every pixel of the CC texture is red, green, blue, pure white or pure black, and each of these **CC colours**
can be kept, recoloured or replaced by the grey texture. What each CC colour covers differs between textures,
so check it in the profile editor.

## The app

The app opens with a **Getting started** guide, and the bar at the top of each tab always says what to do next.
Every section has a **?** button, and **Help** (F1) opens all topics. The full instructions live there, in
[App/HelpText.py](App/HelpText.py), so they're written once and match the app.

In short:

1. **Profile editor tab**: choose a texture set, set a new colour for each CC colour you want to change, press
   **Render** to compare with the original, then **Save profile**. **Show** highlights which part of the texture
   a CC colour covers. Renders are half-size previews unless **Full resolution** is on; zooming in past 50%
   renders every pixel by itself.
2. **Batch tab**: add texture sets to the batch, give them a profile and press **Render**. Texture sets can each
   have their own profile, so a whole armour set (for example `salamanders`, `salamanders_gold_trim` and
   `salamanders_black`) renders in one run. Each profile used gets its own folder,
   `Output/<profile>_<date>_<time>`, always at full resolution.

The app starts in dark mode; switch it off with **Dark mode** at the top right. That choice and the
**Fine-tuning**, **Render automatically** and **Full resolution** switches are remembered in `App/settings.json`.

## Command line

Any arguments run the command line instead of the GUI:

```sh
run.bat --list                          # show available profiles
run.bat salamanders blood_angels        # render all texture sets with these profiles
run.bat --all --workers 4               # every profile, 4 processes
run.bat imperial_fists --only "Snow_*"  # only some texture sets
run.bat --help                          # all options
```

On Linux / macOS use `./run.sh` the same way. The command line skips texture sets whose names only roughly
match; fix their names or render them from the GUI.

## Checking against the example sets

`Examples/Salamanders Pilot` and `Examples/Black Templars Soldier` hold hand-made armour sets: `Base`, `A`, `CC` and
the expected results in `Final`. From the project folder, `App\venv\Scripts\python App\tests\check_dev_example.py`
(`App/venv/bin/python App/tests/check_dev_example.py` on Linux and macOS) renders them with their profiles and
compares every texture with `Final`: parts the final kept must be unchanged, and changed parts must have the same
colour. Add `--only salamanders` or `--only templars` to check one set, and `--sheet compare.png` to save a
side-by-side picture. Run it after changing the recolouring code.

When they're present, it also checks every uniform in `Finals/Salamanders` and `Finals/Black Templar`, and the
original Ultramarine textures in `../Ultramarines Compiled`, made from their grey and CC textures only. Each line
says PASS, FAIL or OPEN. OPEN marks a known difference that needs a decision; the reason is printed under it.

## Profiles

Profiles are stored in [profiles.toml](profiles.toml). The comments at the top of that file explain every setting
for editing it by hand. Profiles saved from the app list every CC colour explicitly, so they don't depend on
`[defaults]`.

Each team has a main profile and variants for parts that differ, such as `_black` for black shoulder pads,
`_gold_trim` where the base texture has no gold yet, and profiles for parts that are unique per set, such as
officer shoulders and helmets. Profiles marked `experimental = true` haven't been checked against finished
textures; the app lists them as experimental.

### How recolouring works

Recolouring works in the OKLab colour space. The typical grey value of a CC colour's area maps to exactly the
new colour. Lighter or darker grey shifts the lightness up or down, limited by how much room the colour has
before reaching black or white, so very dark and very light colours keep their detail.

A part gets less paint where its CC colour is faint, as the game does, so worn edges show the grey texture
(`cc_strength`, fitted to the original game textures; `cc_strength = false` paints a part evenly). Results keep
the transparency of their base texture.

The original algorithm (`colour * (1 - grey brightness)` with hand-tuned lift rules) is still available with
`method = "legacy"` in `profiles.toml`; see the `salamanders_legacy` profile.
