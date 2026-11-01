# blender-addon-kit

Shared build, test and runtime files for my Blender add-ons. Each add-on repo gets copies of the files (`sync_kit.py`), so every repo stays self-contained and the kit only changes when I change it.

## What is in it

    tools/      build.py, _run_all.py, _run_in_blender.py   always synced
    runtime/    auto_load.py, progress.py, updater/         optional extras
    sync_kit.py                                             copies them, detects drift
    tests/      the kit's own tests (fake Blender, no real one needed)

## Start a new add-on repo

Layout the tools expect: one add-on folder in the repo root, plus `tests/`.

    my_addon/                  legacy: __init__.py with bl_info
        __init__.py            extension: blender_manifest.toml (and __init__.py)
    tests/plain/               plain-Python tests (fake bpy), any *.py not starting with _
    tests/blender/             tests run inside real Blender
    LICENSE

The folder name is the add-on id: lowercase letters, digits, underscores, starting with a letter (no hyphens). `build.py` refuses anything else, because Blender and the updater derive module and operator names from it.

    python path/to/kit/sync_kit.py .                       tools only
    python path/to/kit/sync_kit.py . --with auto_load progress
    python path/to/kit/sync_kit.py . --check               what differs from the kit?

Then `python build.py`.

## build.py

    python build.py                 plain tests, Blender tests on the BUILT zip, then dist/<id>-<version>.zip
    python build.py --headless      no window; tests marked "# needs-window" are skipped (and reported)
    python build.py --tests-only    build nothing
    python build.py --repo          extensions: also write dist/repo/ with index.json for hosting
    python build.py --blender PATH  (or set BLENDER)

- Version comes from `bl_info["version"]` (legacy) or `version` in `blender_manifest.toml` (extension), and must be `1.2.3`.
- Legacy zips have a top-level `<id>/` folder; extension zips are flat. The root `LICENSE` is added to the zip.
- Extension `[build] paths_exclude_pattern` is honored (simple matching: names, folders, globs).
- Blender tests run in a temporary settings folder (`BLENDER_USER_*`), one fresh Blender per test file, against the installed built zip, never your own add-ons. Nothing lands in `dist/` unless everything passes.
- Never use `--factory-startup` in these runs: it hides the add-on's own install.

### Blender tests

A file in `tests/blender/` (not starting with `_`) is a script that runs inside Blender with the add-on enabled. It passes when it prints at least one `PASS: ...` line, ends with a line `ALL ... PASSED`, and raises nothing. Put `# needs-window` in its first lines if it needs a real window.

## Updates

**Default: legacy add-on with the vendored updater.** It does not depend on Blender's extension system or on one host. The engine can be switched (GitHub, GitLab, Bitbucket) in one place, and the release zip can be mirrored on several platforms. `--with updater` copies it. It is frozen: bug fixes only.

1. `constants.py` needs `ADDON_ID`, `GITHUB_USER`, `GITHUB_REPO`, `GITHUB_BRANCH = "main"`.
2. `__init__.py` calls `addon_updater_ops.register(bl_info)` in `register()` and `addon_updater_ops.unregister()` in `unregister()`.
3. `preferences.py` has `auto_check_update` and `updater_interval_months/days/hours/minutes` properties, and its `draw()` calls `addon_updater_ops.update_settings_ui(self, context)`. The preferences `bl_idname` must be `__package__`.
4. Releases: name the release exactly like the tag (`v1.0.1`) and attach the zip from `dist/`. The updater downloads the attached zip.

The updater needs the legacy layout (`bl_info`, add-on installed under `scripts/addons`), so `sync_kit.py` refuses it for extensions.

**Optional: extension format.** `build.py` also builds extensions (`blender_manifest.toml`), and `--repo` writes `dist/repo/` (zip plus `index.json`), which is plain static files that can be hosted anywhere. Extensions get Blender's own update mechanism instead of the vendored updater. Not used by any of my add-ons so far.

## Other extras

- `auto_load`: registers every class in the package in dependency order. In `__init__.py`: `auto_load.init()` then `auto_load.register()` / `auto_load.unregister()`.
- `progress`: `with_progress(context, items, minimum=2)` shows Blender's progress cursor for loops with several items and always clears it.

## Changing the kit

Edit the kit, run `python tests/test_kit.py`, then `sync_kit.py` in each repo. Synced files start with a "Shared kit file" header. `sync_kit.py` never overwrites a file you edited by hand (or one that existed before) without `--force`, and `--check` exits 1 when anything differs, so it can run in CI.

## Not yet verified against a real Blender

The extension commands in `build.py` (`extension install-file -r user_default`, `extension server-generate --repo-dir`) and enabling `bl_ext.user_default.<id>` inside an isolated config are written from documentation, not run. The kit's tests use a fake Blender. If the first extension build fails there, it fails loudly with Blender's output; fix it once here.

## Licenses

`tools/` and `sync_kit.py`: MIT. The runtime extras come from other projects (the updater is GPL v2 or later; `auto_load` is MIT, from Jacques Lucke's blender_vscode, and its notice stays in the file header). An add-on that ships the updater must be GPL-compatible. Details are in `THIRD_PARTY_NOTICES.md`.
