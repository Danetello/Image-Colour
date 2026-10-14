import argparse
import multiprocessing
import sys
import time
from datetime import datetime
from pathlib import Path

import ColourHandler
import FileHandler as File
import SystemSupport
from ProfileHandler import ProfileError, loadProfiles


def parseArgs():
    detected = SystemSupport.detectThreads()
    parser = argparse.ArgumentParser(
        description="Recolour Space Marine 2 textures using the profiles in profiles.toml. Run without arguments to open the GUI.",
        epilog="Examples (./run.sh on Linux and macOS):\n"
        "  run.bat                          (opens the GUI)\n"
        "  run.bat --list\n"
        "  run.bat salamanders\n"
        "  run.bat salamanders imperial_fists --only \"Snow_*\"\n"
        "  run.bat --all --workers 4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("profiles", nargs="*", help="profile name(s) to render")
    parser.add_argument("--all", action="store_true", help="render every profile")
    parser.add_argument("--list", action="store_true", help="list the available profiles and exit")
    parser.add_argument("--only", nargs="+", metavar="PATTERN", help="only process textures whose name matches (wildcards allowed)")
    parser.add_argument("--config", type=Path, default=File.PROFILES_FILE, help="profile file (default: profiles.toml)")
    parser.add_argument("--root", type=Path, default=File.TEXTURES_DIR,
                        help="folder holding the Base, Grey and CC folders (default: Textures)")
    parser.add_argument("--out", type=Path, default=File.OUTPUT_DIR,
                        help="output folder (default: Output); each run gets a <profile>_<date>_<time> subfolder")
    workersHelp = f"number of parallel processes (default: all {detected} threads)" if detected else \
        f"number of parallel processes (default: {SystemSupport.FALLBACK_THREADS}, as this processor's threads couldn't be detected)"
    parser.add_argument("--workers", type=int, default=detected or SystemSupport.FALLBACK_THREADS, help=workersHelp)
    return parser.parse_args()


def listProfiles(profiles):
    width = max(len(name) for name in profiles)
    print("Available profiles:")
    for name, profile in profiles.items():
        print(f"  {name:<{width}}  {'(experimental) ' if profile.experimental else ''}{profile.description}")


def runCommandLine(args):
    try:
        profiles = loadProfiles(args.config)
    except ProfileError as e:
        sys.exit(f"Profile error: {e}")

    if args.list or not (args.profiles or args.all):
        listProfiles(profiles)
        return

    selected = list(profiles) if args.all else args.profiles
    unknown = [name for name in selected if name not in profiles]
    if unknown:
        listProfiles(profiles)
        sys.exit(f"\nUnknown profile(s): {', '.join(unknown)}")

    textureSets, warnings = File.findTextureSets(args.root, args.only)
    for warning in warnings:
        print(warning)
    if not textureSets:
        matching = f" matching {' '.join(args.only)}" if args.only else ""
        sys.exit(f"No complete texture sets{matching} found in {args.root}")

    outputRoot = args.out
    started = datetime.now()
    outputDirs = {name: outputRoot / File.outputFolderName(name, started) for name in selected}
    jobs = [(textureSet, profiles[name], outputDirs[name]) for name in selected for textureSet in textureSets]

    workers = max(1, min(args.workers, len(jobs)))
    print(f"Rendering {len(textureSets)} texture(s) x {len(selected)} profile(s) with {workers} worker(s)...")
    start = time.perf_counter()

    if workers == 1:
        results = map(ColourHandler.createRecolour, jobs)
    else:
        pool = multiprocessing.Pool(workers)
        results = pool.imap_unordered(ColourHandler.createRecolour, jobs)

    failures = 0
    for target, error, note in results:
        if error:
            failures += 1
            print(f"  FAILED {target}: {error}")
        else:
            print(f"  {target.relative_to(outputRoot)}" + (f"  ({note})" if note else ""))

    if workers > 1:
        pool.close()
        pool.join()

    print(f"Done in {time.perf_counter() - start:.1f}s" + (f", {failures} failed" if failures else ""))
    if failures:
        sys.exit(1)


def main():
    File.ensureUserFolders()
    if len(sys.argv) == 1:
        import Gui
        Gui.run(File.TEXTURES_DIR, File.PROFILES_FILE, File.SETTINGS_FILE, File.OUTPUT_DIR)
    else:
        runCommandLine(parseArgs())

