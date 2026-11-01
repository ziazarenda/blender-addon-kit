# Third-party notices

The kit's own tools (`tools/`, `sync_kit.py`, `tests/`) are MIT (see `LICENSE`). The runtime extras below come from other projects and keep their own terms.

| Kit file | Origin | License |
|---|---|---|
| `runtime/updater/addon_updater.py`, `addon_updater_ops.py` | CG-Cookie's Blender addon updater, with local changes (hardened zip extraction, release-zip download, settings from `constants.py`, version text) | GPL v2 or later (the notice in the source headers applies) |
| `runtime/updater/vendor/humanize/` | humanize | MIT (`LICENCE` is included in that folder) |
| `runtime/auto_load.py` | the `auto_load` helper from Jacques Lucke's [blender_vscode](https://github.com/JacquesLucke/blender_vscode), with a cycle check added to `toposort` | MIT, Copyright (c) 2018 Jacques Lucke (the full notice is in the file header and must stay there) |
| `runtime/progress.py` | written for this kit | MIT |

## What this means for an add-on that ships them

- An add-on that includes the updater ships GPL-derived code, so it must be released under GPL-compatible terms (GEPrep is GPL-3.0, which satisfies the updater's "v2 or later"). `auto_load` is MIT, so it can go into any add-on as long as its header stays in the file.
- Ship the full license text with the add-on: put the GPL in the repo's `LICENSE`. `build.py` copies it into the zip. The notice in a source header is not a substitute for the license text.
- `sync_kit.py` warns when the updater is synced into a repo whose `LICENSE` is not the GPL.
- Add-ons that use none of the GPL extras (for example `apply_rotation_scale_origin`) are unaffected and can stay MIT.
