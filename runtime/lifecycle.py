# Shared kit file (blender-addon-kit). Do not edit here: change it in the kit
# and run sync_kit.py.
#
# Blender test: disable and re-enable the add-on several times.
# - an error while disabling or enabling fails the test (addon_utils only
#   prints errors unless it is given a handler)
# - enabling again must bring back exactly the properties the add-on attached
#   to Blender's own types (Scene, Object, ...)
import os

import addon_utils

import bpy

module = os.environ["ADDON_MODULE"]
ROUNDS = 3
checks = 0


def fail(error):
    raise error


def check(name, condition):
    global checks
    assert condition, name
    checks += 1
    print("PASS:", name)


def loaded():
    return bool(addon_utils.check(module)[1])


def snapshot():
    """Property names of Blender's ID types (and bones), where add-ons attach data."""
    types = list(bpy.types.ID.__subclasses__())
    types += [getattr(bpy.types, name) for name in ("Bone", "PoseBone", "EditBone")
              if hasattr(bpy.types, name)]
    return {cls.__name__: frozenset(cls.bl_rna.properties.keys()) for cls in types}


enabled = snapshot()
check("the add-on is enabled at the start", loaded())

for number in range(1, ROUNDS + 1):
    addon_utils.disable(module, default_set=False, handle_error=fail)
    check(f"round {number}: the add-on is disabled", not loaded())

    disabled = snapshot()
    added = sum(len(enabled[name] - disabled.get(name, frozenset())) for name in enabled)
    check(f"round {number}: disabling added no properties",
          all(disabled[name] <= enabled.get(name, frozenset()) for name in disabled))
    print(f"INFO: round {number}: the add-on attaches {added} properties to Blender's types")

    addon_utils.enable(module, default_set=False, persistent=False, handle_error=fail)
    check(f"round {number}: the add-on is enabled again", loaded())
    check(f"round {number}: the same properties are back", snapshot() == enabled)

print(f"\nALL {checks} CHECKS PASSED")
