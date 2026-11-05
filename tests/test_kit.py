"""The kit's own tests. Plain Python, no Blender:  python tests/test_kit.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
FAKE = Path(__file__).resolve().parent / "fake_blender.py"

PASSING_TEST = 'print("PASS: one")\nprint("PASS: two")\nprint("ALL CHECKS PASSED")\n'
WINDOW_TEST = "# needs-window\n" + PASSING_TEST

LEGACY_INIT = '''bl_info = {"name": "Demo", "version": (1, 2, 3), "blender": (4, 0, 0)}

def register(): pass
def unregister(): pass
'''

MANIFEST = '''schema_version = "1.0.0"
id = "demo_ext"
version = "0.4.0"
name = "Demo"
tagline = "Demo"
maintainer = "Me <me@example.com>"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:MIT"]

[build]
paths_exclude_pattern = ["__pycache__/", "*.blend1", "scratch/"]
'''


def make_repo(kind="legacy", addon_id=None, init=None, tests=None, license_text="MIT"):
    root = Path(tempfile.mkdtemp(prefix="kit-test-"))
    addon_id = addon_id or ("demo" if kind == "legacy" else "demo_ext")
    addon = root / addon_id
    addon.mkdir()
    (addon / "__init__.py").write_text(init or ("" if kind == "extension" else LEGACY_INIT))

    if kind == "extension":
        (addon / "blender_manifest.toml").write_text(MANIFEST.replace("demo_ext", addon_id))

    if license_text:
        (root / "LICENSE").write_text(license_text)

    for sub in ("tests/plain", "tests/blender"):
        (root / sub).mkdir(parents=True)

    shutil.copy(KIT / "tools" / "build.py", root / "build.py")
    shutil.copy(KIT / "tools" / "_run_all.py", root / "tests/plain/_run_all.py")
    shutil.copy(KIT / "tools" / "_run_in_blender.py", root / "tests/blender/_run_in_blender.py")

    for name, body in (tests or {}).items():
        (root / "tests/blender" / name).write_text(body)

    return root


def build(root, *args):
    return subprocess.run([sys.executable, "build.py", "--blender", str(FAKE), *args],
                          cwd=root, capture_output=True, text=True)


class BuildTests(unittest.TestCase):
    def tearDown(self):
        for path in getattr(self, "roots", []):
            shutil.rmtree(path, ignore_errors=True)

    def repo(self, *args, **kwargs):
        root = make_repo(*args, **kwargs)
        self.roots = getattr(self, "roots", []) + [root]
        return root

    def names(self, root, zip_name):
        return zipfile.ZipFile(root / "dist" / zip_name).namelist()

    def test_legacy_zip_has_top_folder_and_license(self):
        root = self.repo(tests={"a.py": PASSING_TEST})
        (root / "demo" / "__pycache__").mkdir()
        (root / "demo" / "__pycache__" / "x.pyc").write_bytes(b"x")
        result = build(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        names = self.names(root, "demo-1.2.3.zip")
        self.assertIn("demo/__init__.py", names)
        self.assertIn("demo/LICENSE", names)
        self.assertFalse([n for n in names if "pycache" in n or n.startswith("tests")])

    def test_extension_zip_is_flat_and_honors_excludes(self):
        root = self.repo("extension", tests={"a.py": PASSING_TEST})
        (root / "demo_ext" / "scratch").mkdir()
        (root / "demo_ext" / "scratch" / "junk.txt").write_text("x")
        (root / "demo_ext" / "model.blend1").write_text("x")
        result = build(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        names = self.names(root, "demo_ext-0.4.0.zip")
        self.assertIn("blender_manifest.toml", names)
        self.assertIn("__init__.py", names)
        self.assertIn("LICENSE", names)
        self.assertFalse([n for n in names if "scratch" in n or n.endswith(".blend1")])

    def test_zip_is_reproducible(self):
        root = self.repo(tests={"a.py": PASSING_TEST})
        build(root)
        first = (root / "dist" / "demo-1.2.3.zip").read_bytes()
        build(root)
        self.assertEqual(first, (root / "dist" / "demo-1.2.3.zip").read_bytes())

    def test_failing_blender_test_builds_nothing(self):
        root = self.repo(tests={"bad.py": 'print("PASS: x")\nraise RuntimeError("boom")\n'})
        result = build(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / "dist").exists())
        self.assertIn("boom", result.stdout)

    def test_test_without_finish_line_fails(self):
        root = self.repo(tests={"half.py": 'print("PASS: x")\n'})
        self.assertNotEqual(build(root).returncode, 0)

    def test_needs_window_is_skipped_headless_and_run_otherwise(self):
        root = self.repo(tests={"w.py": WINDOW_TEST})
        headless = build(root, "--headless")
        self.assertEqual(headless.returncode, 0, headless.stdout)
        self.assertIn("skipped", headless.stdout)
        self.assertIn("WARNING: not run", headless.stdout)
        windowed = build(root)
        self.assertEqual(windowed.returncode, 0, windowed.stdout)
        self.assertIn("passed", windowed.stdout)

    def test_info_lines_of_passing_tests_are_shown(self):
        test = 'print("INFO: hello from the test")\nprint("PASS: one")\nprint("ALL OK PASSED")\n'
        root = self.repo(tests={"a.py": test})
        result = build(root)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("INFO: hello from the test", result.stdout)
        self.assertNotIn("PASS: one", result.stdout)

    def test_runner_tests_the_built_zip_not_the_source(self):
        # Excluded files must be missing from what the test sees.
        test = ('import os\nroot = os.environ["ADDON_ROOT"]\n'
                'assert not os.path.exists(os.path.join(root, "model.blend1")), "excluded file shipped"\n'
                'print("PASS: ok")\nprint("ALL OK PASSED")\n')
        root = self.repo("extension", tests={"a.py": test})
        (root / "demo_ext" / "model.blend1").write_text("x")
        result = build(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bad_ids_are_rejected(self):
        for bad in ("my-addon", "My_Addon", "1abc"):
            root = self.repo(addon_id=bad)
            result = build(root, "--skip-blender")
            self.assertNotEqual(result.returncode, 0, bad)
            self.assertIn("not a valid add-on id", result.stdout)

    def test_bad_version_rejected(self):
        root = self.repo(init=LEGACY_INIT.replace("(1, 2, 3)", "(1, 2)"))
        result = build(root, "--skip-blender")
        self.assertNotEqual(result.returncode, 0)

    def test_two_addons_rejected(self):
        root = self.repo()
        other = root / "other"
        other.mkdir()
        (other / "__init__.py").write_text(LEGACY_INIT)
        self.assertIn("more than one", build(root, "--skip-blender").stdout)

    def test_license_inside_the_addon_is_not_duplicated_or_warned_about(self):
        root = self.repo(tests={"a.py": PASSING_TEST})
        (root / "demo" / "LICENSES.txt").write_text("notices")
        result = build(root)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("no LICENSE", result.stdout)
        names = self.names(root, "demo-1.2.3.zip")
        self.assertIn("demo/LICENSES.txt", names)
        self.assertNotIn("demo/LICENSE", names)

    def test_license_inside_the_addon_without_a_root_license(self):
        root = self.repo(license_text=None)
        (root / "demo" / "LICENSES.txt").write_text("notices")
        result = build(root, "--skip-blender")
        self.assertNotIn("no LICENSE", result.stdout)

    def test_missing_license_warns(self):
        root = self.repo(license_text=None)
        result = build(root, "--skip-blender")
        self.assertEqual(result.returncode, 0)
        self.assertIn("no LICENSE", result.stdout)

    def test_plain_test_failure_stops_before_build(self):
        root = self.repo(tests={"a.py": PASSING_TEST})
        (root / "tests/plain/boom.py").write_text("raise SystemExit(3)\n")
        result = build(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / "dist").exists())

    def test_tests_only_builds_nothing(self):
        root = self.repo(tests={"a.py": PASSING_TEST})
        self.assertEqual(build(root, "--tests-only").returncode, 0)
        self.assertFalse((root / "dist").exists())

    def test_repo_flag_writes_index(self):
        root = self.repo("extension", tests={"a.py": PASSING_TEST})
        result = build(root, "--repo")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((root / "dist/repo/index.json").exists())
        self.assertTrue((root / "dist/repo/demo_ext-0.4.0.zip").exists())
        self.assertNotEqual(build(self.repo(), "--repo").returncode, 0)

    def test_blender_missing_is_loud(self):
        root = self.repo(tests={"a.py": PASSING_TEST})
        env = dict(os.environ, PATH="/nonexistent", BLENDER="")
        # build.py also tries fixed locations such as /usr/bin/blender, which exist on
        # many machines. Empty that list so the test does not depend on the computer.
        code = ("import importlib.util, sys\n"
                "spec = importlib.util.spec_from_file_location('kit_build', 'build.py')\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "module.BLENDER_FALLBACKS = ()\n"
                "sys.argv = ['build.py', '--blender', '/nope']\n"
                "module.main()\n")
        result = subprocess.run([sys.executable, "-c", code], cwd=root,
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Blender not found", result.stdout)


def sync(repo, *args):
    return subprocess.run([sys.executable, str(KIT / "sync_kit.py"), str(repo), *args],
                          capture_output=True, text=True)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        # start from a bare repo: no tools yet
        (self.root / "build.py").unlink()
        shutil.rmtree(self.root / "tests")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_first_sync_adds_tools_and_manifest(self):
        result = sync(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "build.py").exists())
        self.assertTrue((self.root / "tests/blender/_run_in_blender.py").exists())
        manifest = json.loads((self.root / ".kit.json").read_text())
        self.assertIn("build.py", manifest["files"])

    def test_extras_are_remembered(self):
        sync(self.root, "--with", "progress", "auto_load")
        self.assertTrue((self.root / "demo/helpers/progress.py").exists())
        self.assertTrue((self.root / "demo/helpers/__init__.py").exists())
        self.assertTrue((self.root / "demo/auto_load.py").exists())
        sync(self.root)
        self.assertEqual(json.loads((self.root / ".kit.json").read_text())["extras"], ["auto_load", "progress"])

    def test_lifecycle_extra_goes_to_the_blender_tests(self):
        sync(self.root, "--with", "lifecycle")
        self.assertTrue((self.root / "tests/blender/lifecycle.py").exists())
        self.assertIn("lifecycle", json.loads((self.root / ".kit.json").read_text())["extras"])

    def test_check_reports_and_changes_nothing(self):
        sync(self.root)
        (self.root / "build.py").write_text("# edited\n")
        before = (self.root / ".kit.json").read_text()
        result = sync(self.root, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("EDITED HERE", result.stdout)
        self.assertEqual((self.root / "build.py").read_text(), "# edited\n")
        self.assertEqual((self.root / ".kit.json").read_text(), before)

    def test_clean_check_is_zero(self):
        sync(self.root)
        self.assertEqual(sync(self.root, "--check").returncode, 0)

    def test_edited_file_kept_until_force(self):
        sync(self.root)
        (self.root / "build.py").write_text("# edited\n")
        self.assertEqual(sync(self.root).returncode, 1)
        self.assertEqual((self.root / "build.py").read_text(), "# edited\n")
        self.assertEqual(sync(self.root, "--force").returncode, 0)
        self.assertEqual((self.root / "build.py").read_bytes(), (KIT / "tools/build.py").read_bytes())

    def test_existing_unmanaged_file_needs_force(self):
        (self.root / "build.py").write_text("# my own\n")
        result = sync(self.root)
        self.assertIn("EXISTS", result.stdout)
        self.assertEqual((self.root / "build.py").read_text(), "# my own\n")

    def test_outdated_file_updates(self):
        sync(self.root)
        manifest = json.loads((self.root / ".kit.json").read_text())
        old = b"# old kit version\n"
        (self.root / "build.py").write_bytes(old)
        import hashlib
        manifest["files"]["build.py"] = hashlib.sha256(old).hexdigest()
        (self.root / ".kit.json").write_text(json.dumps(manifest))
        self.assertEqual(sync(self.root, "--check").returncode, 1)
        self.assertEqual(sync(self.root).returncode, 0)
        self.assertEqual((self.root / "build.py").read_bytes(), (KIT / "tools/build.py").read_bytes())

    def test_dry_run_writes_nothing(self):
        sync(self.root, "--dry-run")
        self.assertFalse((self.root / "build.py").exists())
        self.assertFalse((self.root / ".kit.json").exists())

    def test_updater_extra_and_constants_note(self):
        result = sync(self.root, "--with", "updater")
        self.assertTrue((self.root / "demo/addon_updater_ops.py").exists())
        self.assertTrue((self.root / "demo/vendor/humanize/__init__.py").exists())
        self.assertIn("GITHUB_USER", result.stdout)

    def test_updater_refused_for_extensions(self):
        shutil.rmtree(self.root)
        self.root = make_repo("extension")
        self.assertNotEqual(sync(self.root, "--with", "updater").returncode, 0)
        self.assertFalse((self.root / "demo_ext/addon_updater.py").exists())


class RuntimeTests(unittest.TestCase):
    def test_runner_tee_survives_missing_stdout(self):
        source = (KIT / "tools/_run_in_blender.py").read_text()
        self.assertIn("if stream is not None", source)

    def test_runner_uses_background_flag_not_window(self):
        source = (KIT / "tools/_run_in_blender.py").read_text()
        self.assertIn("needs_window(source) and bpy.app.background", source)

    def test_license_warning_for_non_gpl_repo(self):
        root = make_repo()
        try:
            self.assertIn("GPL-derived", sync(root, "--with", "updater").stdout)
            (root / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\nVersion 3")
            self.assertNotIn("GPL-derived", sync(root, "--with", "updater").stdout)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_auto_load_keeps_its_mit_notice(self):
        head = (KIT / "runtime/auto_load.py").read_text(encoding="utf-8")[:3000]
        self.assertIn("Copyright (c) 2018 Jacques Lucke", head)
        self.assertIn("Permission is hereby granted", head)

    def test_runtime_files_are_neutral(self):
        for path in (KIT / "runtime").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("geprep", text.lower(), path)

    def test_runtime_files_compile_and_carry_the_header(self):
        for path in (KIT / "runtime").rglob("*.py"):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

            if "vendor" not in path.parts:
                self.assertIn("Shared kit file", path.read_text(encoding="utf-8")[:200], path)

    def test_progress_helper(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("kit_progress", KIT / "runtime/progress.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        calls = []
        manager = type("M", (), {"progress_begin": lambda s, a, b: calls.append(("begin", b)),
                                 "progress_update": lambda s, v: calls.append(("update", v)),
                                 "progress_end": lambda s: calls.append(("end",))})()
        context = type("C", (), {"window_manager": manager})()
        self.assertEqual(list(module.with_progress(context, [1])), [1])
        self.assertEqual(calls, [])
        self.assertEqual(list(module.with_progress(context, [1, 2, 3])), [1, 2, 3])
        self.assertEqual(calls[0], ("begin", 3))
        self.assertEqual(calls[-1], ("end",))
        calls.clear()

        with self.assertRaises(ValueError):
            for _ in module.with_progress(context, [1, 2]):
                raise ValueError

        self.assertEqual(calls[-1], ("end",))

    def test_auto_load_toposort_detects_cycles(self):
        import importlib.util
        import types
        fake_bpy = types.ModuleType("bpy")
        fake_bpy.app = types.SimpleNamespace(version=(4, 0, 0))
        sys.modules.setdefault("bpy", fake_bpy)
        spec = importlib.util.spec_from_file_location("kit_auto_load", KIT / "runtime/auto_load.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class A: pass
        class B: pass
        class C: pass

        self.assertEqual(module.toposort({A: set(), B: {A}, C: {B}}), [A, B, C])

        with self.assertRaises(RuntimeError) as caught:
            module.toposort({A: {B}, B: {A}, C: set()})

        self.assertIn("A, B", str(caught.exception))

    def test_auto_load_unregisters_in_the_reverse_order_of_register(self):
        import importlib.util
        import types
        from unittest import mock

        order = []
        fake_bpy = types.ModuleType("bpy")
        fake_bpy.app = types.SimpleNamespace(version=(4, 0, 0))
        fake_bpy.utils = types.SimpleNamespace(
            register_class=lambda cls: order.append(("register_class", cls.__name__)),
            unregister_class=lambda cls: order.append(("unregister_class", cls.__name__)))

        with mock.patch.dict(sys.modules, {"bpy": fake_bpy}):
            spec = importlib.util.spec_from_file_location("kit_auto_load_order", KIT / "runtime/auto_load.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        class A: pass
        class B: pass

        def part(name, with_hooks=True):
            hooks = {"register": lambda: order.append(("register", name)),
                     "unregister": lambda: order.append(("unregister", name))} if with_hooks else {}
            return types.SimpleNamespace(__name__=name, **hooks)

        module.ordered_classes = [A, B]
        module.modules = [part("first"), part("no_hooks", False), part("second")]
        module.register()
        order.append(("--",))
        module.unregister()

        self.assertEqual(order, [
            ("register_class", "A"), ("register_class", "B"),
            ("register", "first"), ("register", "second"),
            ("--",),
            ("unregister", "second"), ("unregister", "first"),
            ("unregister_class", "B"), ("unregister_class", "A"),
        ])

    def test_lifecycle_test_fails_on_errors_and_ends_with_the_finish_line(self):
        source = (KIT / "runtime/lifecycle.py").read_text(encoding="utf-8")
        self.assertIn("handle_error=fail", source)
        self.assertIn('print(f"\\nALL {checks} CHECKS PASSED")', source)
        self.assertIn('ADDON_MODULE', source)

    def test_updater_version_text(self):
        source = (KIT / "runtime/updater/addon_updater_ops.py").read_text()
        start = source.index("def _version_text")
        namespace = {}
        exec(source[start:source.index("\n\n", start + 200)], namespace)
        self.assertEqual(namespace["_version_text"]((1, 0, 1)), "1.0.1")
        self.assertEqual(namespace["_version_text"]("1.0.1"), "1.0.1")


if __name__ == "__main__":
    unittest.main(verbosity=1)
