#!/usr/bin/env python3
"""A stand-in for the blender executable, for testing the kit without Blender.

Understands just what build.py asks of it:
  --command extension install-file -r REPO ZIP    unpack a flat zip into the extensions folder
  --command extension server-generate --repo-dir D  write D/index.json
  [--background] --python RUNNER -- TEST           run the real runner with fake bpy/addon_utils
"""
import importlib
import os
import runpy
import sys
import types
import zipfile
from pathlib import Path

args = sys.argv[1:]

# Real Blender silently ignores a BLENDER_USER_* folder that does not exist
# and uses the real profile instead, so the fake treats that as a failure.
for name in ("SCRIPTS", "CONFIG", "DATAFILES", "EXTENSIONS"):
    folder = os.environ.get(f"BLENDER_USER_{name}")
    assert folder and Path(folder).is_dir(), f"BLENDER_USER_{name} must be an existing folder: {folder}"

if "--command" in args:
    rest = args[args.index("--command") + 1:]
    assert rest[0] == "extension", rest

    if rest[1] == "install-file":
        archive = Path(rest[-1])
        repo = rest[rest.index("-r") + 1]
        name = zipfile.ZipFile(archive).read("blender_manifest.toml").decode()
        addon_id = [l for l in name.splitlines() if l.startswith("id")][0].split('"')[1]
        target = Path(os.environ["BLENDER_USER_EXTENSIONS"]) / repo / addon_id
        target.mkdir(parents=True)
        zipfile.ZipFile(archive).extractall(target)
        sys.exit(0)

    if rest[1] == "server-generate":
        Path(rest[rest.index("--repo-dir") + 1], "index.json").write_text('{"data": []}')
        sys.exit(0)

    sys.exit(2)

background = "--background" in args
runner = args[args.index("--python") + 1]
sys.argv = ["blender"] + args[args.index("--"):]

bpy = types.ModuleType("bpy")
bpy.app = types.SimpleNamespace(background=background, timers=types.SimpleNamespace(register=lambda f, first_interval=0: f()))
bpy.context = types.SimpleNamespace(window=None if background else object())
bpy.ops = types.SimpleNamespace(wm=types.SimpleNamespace(quit_blender=lambda: None))
sys.modules["bpy"] = bpy

addon_utils = types.ModuleType("addon_utils")


def enable(name, default_set=False, persistent=False):
    scripts = Path(os.environ["BLENDER_USER_SCRIPTS"]) / "addons"

    if name.startswith("bl_ext.user_default."):
        folder = Path(os.environ["BLENDER_USER_EXTENSIONS"]) / "user_default"
        short = name.rsplit(".", 1)[1]
        sys.path.insert(0, str(folder))
        alias = importlib.import_module(short)
        sys.modules[name] = alias
        return alias

    sys.path.insert(0, str(scripts))
    try:
        return importlib.import_module(name)
    except Exception:
        return None


addon_utils.enable = enable
sys.modules["addon_utils"] = addon_utils
runpy.run_path(runner, run_name="__main__")
