#!/usr/bin/env python3
"""Copy the shared kit files into an add-on repo, and tell you when they drift.

    python sync_kit.py ../my_addon                          tools only (first time)
    python sync_kit.py ../my_addon --with auto_load progress
    python sync_kit.py ../my_addon --with updater           (legacy add-ons only)
    python sync_kit.py ../my_addon --check                  report only, change nothing
    python sync_kit.py ../my_addon --dry-run                show what would change
    python sync_kit.py ../my_addon --force                  overwrite files you edited

Always synced (the tools):
    build.py                    -> <repo>/build.py
    _run_all.py                 -> <repo>/tests/plain/_run_all.py
    _run_in_blender.py          -> <repo>/tests/blender/_run_in_blender.py

Optional extras (--with, remembered in <repo>/.kit.json):
    auto_load  -> <addon>/auto_load.py
    progress   -> <addon>/helpers/progress.py   (with_progress for long loops)
    updater    -> <addon>/addon_updater.py, addon_updater_ops.py, vendor/humanize
                  (GitHub updater for LEGACY add-ons, the default update path.
                  Not for extensions. Configure it in the
                  add-on's constants.py: ADDON_ID, GITHUB_USER, GITHUB_REPO.)

A file is only overwritten when it is unchanged since the last sync, or when it
is byte-identical to the kit's. A file you edited by hand, or one that already
existed before the kit managed it, is reported and left alone unless --force.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
MANIFEST = ".kit.json"
EXTRAS = ("auto_load", "progress", "updater")

REQUIRED_CONSTANTS = ("ADDON_ID", "GITHUB_USER", "GITHUB_REPO", "GITHUB_BRANCH")


def load_build():
    spec = importlib.util.spec_from_file_location("kit_build", KIT / "tools" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data):
    return hashlib.sha256(data).hexdigest()


def plan(addon_dir_name, extras):
    """List (source path in the kit, destination relative to the repo)."""
    pairs = [
        (KIT / "tools" / "build.py", "build.py"),
        (KIT / "tools" / "_run_all.py", "tests/plain/_run_all.py"),
        (KIT / "tools" / "_run_in_blender.py", "tests/blender/_run_in_blender.py"),
    ]
    base = addon_dir_name

    if "auto_load" in extras:
        pairs.append((KIT / "runtime" / "auto_load.py", f"{base}/auto_load.py"))

    if "progress" in extras:
        pairs.append((KIT / "runtime" / "progress.py", f"{base}/helpers/progress.py"))

    if "updater" in extras:
        updater = KIT / "runtime" / "updater"

        for path in sorted(updater.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                pairs.append((path, f"{base}/{path.relative_to(updater).as_posix()}"))

    return pairs


def read_manifest(repo):
    path = repo / MANIFEST

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    return {"extras": [], "files": {}}


def status_of(source, destination, recorded):
    """One of: new, ok, outdated, modified, unmanaged."""
    wanted = digest(source.read_bytes())

    if not destination.exists():
        return "new"

    current = digest(destination.read_bytes())

    if current == wanted:
        return "ok"

    if recorded is None:
        return "unmanaged"    # exists, never synced from the kit

    return "outdated" if current == recorded else "modified"


def addon_name(repo):
    build = load_build()
    addon = build.find_addon(repo)
    return addon.path.name, addon.kind


def check_constants(repo, base):
    path = repo / base / "constants.py"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    missing = [name for name in REQUIRED_CONSTANTS if not any(l.startswith(f"{name} ") or l.startswith(f"{name}=") for l in text.splitlines())]

    if missing:
        print(f"\nNOTE: {base}/constants.py needs these for the updater: {', '.join(missing)}")
        print('  ADDON_ID = "my_addon"   # same as the folder name\n'
              '  GITHUB_USER = "you"\n  GITHUB_REPO = "my-addon"\n  GITHUB_BRANCH = "main"')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", help="the add-on repo to update")
    parser.add_argument("--with", dest="extras", nargs="*", default=[], choices=EXTRAS, metavar="EXTRA",
                        help="extras to add: " + ", ".join(EXTRAS))
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if anything differs")
    parser.add_argument("--dry-run", action="store_true", help="show what would change")
    parser.add_argument("--force", action="store_true", help="overwrite edited / unmanaged files")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()

    if not repo.is_dir():
        sys.exit(f"Not a folder: {repo}")

    base, kind = addon_name(repo)
    manifest = read_manifest(repo)
    extras = sorted(set(manifest["extras"]) | set(args.extras))

    if "updater" in extras and kind == "extension":
        sys.exit("The updater extra is for legacy add-ons. It needs the legacy layout (bl_info).")

    pairs = plan(base, extras)
    files = dict(manifest["files"])
    changed = problems = 0

    print(f"{repo.name}: {base} ({kind}); extras: {', '.join(extras) or 'none'}")

    for source, relative in pairs:
        destination = repo / relative
        state = status_of(source, destination, files.get(relative))
        write = state in ("new", "outdated") or (state in ("modified", "unmanaged") and args.force)
        label = {"new": "add", "outdated": "update", "ok": "ok", "modified": "EDITED HERE", "unmanaged": "EXISTS"}[state]

        if state in ("modified", "unmanaged") and not args.force:
            problems += 1
            label += " (kept; --force overwrites)"
        elif write:
            changed += 1
            label = label if state in ("new", "outdated") else "overwrite"

        print(f"  {label:34} {relative}")

        if write and not (args.check or args.dry_run):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            files[relative] = digest(source.read_bytes())
        elif state == "ok":
            files[relative] = digest(source.read_bytes())

    # helpers/ must be a package for the progress extra
    if "progress" in extras:
        init = repo / base / "helpers" / "__init__.py"

        if not init.exists():
            changed += 1
            print(f"  {'add':34} {base}/helpers/__init__.py")

            if not (args.check or args.dry_run):
                init.parent.mkdir(parents=True, exist_ok=True)
                init.write_text("", encoding="utf-8")

    if "updater" in extras:
        license_text = "".join(p.read_text(encoding="utf-8", errors="replace")
                               for p in sorted(repo.glob("LICENSE*")))

        if "GNU GENERAL PUBLIC LICENSE" not in license_text.upper():
            print("\nWARNING: the updater files are GPL-derived (see THIRD_PARTY_NOTICES.md). "
                  "This repo's LICENSE is not the GPL, so the add-on must be GPL-compatible before you ship it.")

    if "updater" in extras:
        check_constants(repo, base)

    if args.check or args.dry_run:
        print(f"\n{changed} would change, {problems} need a decision." if changed or problems else "\nUp to date.")
        return 1 if (args.check and (changed or problems)) else 0

    manifest = {"extras": extras, "files": files}
    (repo / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\n{changed} written, {problems} kept." + (" Review the kept files, then rerun with --force if you want the kit's version." if problems else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
