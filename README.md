# Foxhole: Space Marine 2 Image Colouring Tool

Recolours the Space Marine 2 uniform textures for the Foxhole: Space Marine Uniform Mod. Build a profile
visually, then render whole batches of textures with it.

## Setup and running

Requires **Python 3.12 or newer** (checked by the scripts and at startup).

| Windows                | Linux / macOS        | What it does                                                        |
|------------------------|----------------------|---------------------------------------------------------------------|
| `run.bat`              | `./run.sh`           | Starts the app. Sets up the virtual environment first when needed. |
| `install_venv.bat`     | `./install_venv.sh`  | Creates or updates the virtual environment in `venv` on its own.   |

`run` sets up the environment automatically when `venv` is missing or `requirements.txt` has changed.
On Linux the GUI needs tkinter, e.g. `sudo apt install python3-tk`.

## Textures

Each texture set is three files, matched by name:

| Folder          | Contents                           | Example                  |
|-----------------|------------------------------------|--------------------------|
| `Textures_Base` | the original (Ultramarine) texture | `Snow_Shoulder_R.png`    |
| `Textures_Grey` | the grey texture, suffix `_a`      | `Snow_Shoulder_R_a.png`  |
| `Textures_Mask` | the CC texture, suffix `_cc`       | `Snow_Shoulder_R_cc.png` |

The folders can also be called `Base`, `Grey` or `A`, and `Mask` or `CC`. An extra CC texture such as
`Pilot_Helmet_checker_cc.png` next to `Pilot_Helmet.png` becomes its own texture set (alternative decals), and a
CC file that is a copy of the base texture is recognised and saved unchanged.

Every pixel of the CC texture is red, green, blue, pure white or pure black, and each of these **CC colours**
can be kept, recoloured or replaced by the grey texture. What each CC colour covers differs between textures,
so check it in the profile editor.

## The app

The app opens with a **Getting started** guide, and the bar at the top of each tab always says what to do next.
Every section has a **?** button, and **Help** (F1) opens all topics. The full instructions live there, in
[HelpText.py](HelpText.py), so they're written once and match the app.

In short:

1. **Profile editor tab**: choose a texture set, set a new colour for each CC colour you want to change, press
   **Render** to compare with the original, then **Save profile**. **Show** highlights which part of the texture
   a CC colour covers.
2. **Batch tab**: add texture sets to the batch, give them a profile and press **Render**. Texture sets can each
   have their own profile, so a whole armour set (for example `salamanders`, `salamanders_helmet` and
   `salamanders_shoulders`) renders in one run. Each profile used gets its own folder,
   `output/<profile>_<date>_<time>`.

The app starts in dark mode; switch it off with **Dark mode** at the top right. That choice and the
**Fine-tuning** and **Render automatically** switches are remembered in `settings.json`.

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

`Dev Example` (Salamanders) and `Dev Example Soldier Templar/Soldier` (Black Templars) hold hand-made armour sets:
`Base`, `A`, `CC` and the expected results in `Final`. `python tests/check_dev_example.py` renders both with their
profiles and compares every texture with `Final`: parts the final kept must be unchanged, and changed parts must
have the same colour. Add `--only salamanders` or `--only templars` to check one set, and `--sheet compare.png` to
save a side-by-side picture. Run it after changing the recolouring code.

## Profiles

Profiles are stored in [profiles.toml](profiles.toml). The comments at the top of that file explain every setting
for editing it by hand. Profiles saved from the app list every CC colour explicitly, so they don't depend on
`[defaults]`.

### How recolouring works

Recolouring works in the OKLab colour space. The typical grey value of a CC colour's area maps to exactly the
new colour. Lighter or darker grey shifts the lightness up or down, limited by how much room the colour has
before reaching black or white, so very dark and very light colours keep their detail.

The original algorithm (`colour * (1 - grey brightness)` with hand-tuned lift rules) is still available with
`method = "legacy"` in `profiles.toml`; see the `salamanders_legacy` profile.
