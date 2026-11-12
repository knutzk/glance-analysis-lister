# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Controlled API mutations verify the advisory checker against real Python."""

import json
import os
import shutil
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.check_public_api import capture, compare, signature, signature_issues

ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "scripts/public_api.toml"


class PublicApiCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        cls.work = Path(cls.temp.name)
        cls.before = capture(ROOT, SURFACE, cls.work / "before.json")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_attrs_signatures_reexports_and_properties_are_captured(self):
        self.assertEqual(compare(self.before, self.before), [])
        self.assertEqual(
            [p["name"] for p in self.before["callables"]["PublicationPolicy"]],
            ["title", "groups", "subgroups", "keywords"],
        )
        self.assertEqual(self.before["callables"]["GroupProfile"][0]["required"], True)
        self.assertEqual(
            self.before["callables"]["CuratedRegistry.from_json"][0]["name"], "path"
        )
        self.assertEqual(
            self.before["callables"]["CuratedRegistry.records"][0]["name"], "resource"
        )
        self.assertTrue(self.before["attributes"]["GroupView.archive"])
        self.assertNotIn("GroupView.controls", self.before["attributes"])
        self.assertNotIn("GroupView", self.before["callables"])

    def mutated(self, change):
        with TemporaryDirectory(dir=self.work) as directory:
            root = Path(directory)
            shutil.copytree(
                ROOT / "grove",
                root / "grove",
                ignore=shutil.ignore_patterns(
                    "__pycache__", "events.py", "event_labels.py"
                ),
            )
            change(root)
            return capture(root, SURFACE, root / "after.json")

    def test_actual_removed_method_is_detected(self):
        def change(root):
            path = root / "grove/registry/reader.py"
            path.write_text(
                path.read_text().replace(
                    "def records(self, resource):", "def _records(self, resource):"
                )
            )

        findings = compare(self.before, self.mutated(change))
        self.assertTrue(
            any("CuratedRegistry.records" in item for item in findings), findings
        )

    def test_removed_package_does_not_fall_back_to_installed_copy(self):
        with TemporaryDirectory(dir=self.work) as directory:
            root = Path(directory)
            after = capture(root, SURFACE, root / "after.json")
        self.assertIsNone(after["callables"]["CuratedRegistry"])
        self.assertTrue(compare(self.before, after))

    def test_actual_incompatible_parameter_is_detected(self):
        def change(root):
            path = root / "grove/registry/reader.py"
            path.write_text(
                path.read_text().replace(
                    "def records(self, resource):", "def records(self, *, resource):"
                )
            )

        findings = compare(self.before, self.mutated(change))
        self.assertIn(
            "CuratedRegistry.records: a previously accepted call no longer binds",
            findings,
        )

    def test_internal_refactor_and_optional_parameter_are_compatible(self):
        def change(root):
            path = root / "grove/registry/reader.py"
            path.write_text(
                path.read_text().replace(
                    "def records(self, resource):",
                    "def records(self, resource, *, extra=None):",
                )
                + "\n\ndef _internal_helper(value):\n    return value\n"
            )
            registry = root / "grove/registry"
            path.rename(registry / "_reader_impl.py")
            (registry / "reader.py").write_text(
                "from ._reader_impl import CuratedRegistry, LINK_RESOURCES\n"
            )

        self.assertEqual(compare(self.before, self.mutated(change)), [])

    def test_removed_scope_entry_cannot_hide_a_break(self):
        after = deepcopy(self.before)
        del after["callables"]["CuratedRegistry.get"]
        del after["attributes"]["GroupView.archive"]
        after["imports"]["prepare_group"] = "grove.other:prepare_group"
        findings = compare(self.before, after)
        self.assertTrue(any("CuratedRegistry.get" in item for item in findings))
        self.assertTrue(any("GroupView.archive" in item for item in findings))
        self.assertIn("prepare_group: documented import path changed", findings)

    def test_parameter_defaults_order_and_required_additions(self):
        cases = [
            (lambda a, b=1: None, lambda a, b=2: None),
            (lambda a, b: None, lambda b, a: None),
            (lambda a: None, lambda a, b: None),
            (lambda a, b=1: None, lambda a, b: None),
            (lambda a, *, b=1: None, lambda a, /, b=1: None),
            (lambda a, *args, **kwargs: None, lambda a: None),
        ]
        for old, new in cases:
            with self.subTest(old=old, new=new):
                before = signature(old)
                after = signature(new)
                self.assertTrue(signature_issues(before, after))
        self.assertFalse(
            signature_issues(
                signature(lambda a: None), signature(lambda a, *, extra=None: None)
            )
        )

    def test_base_inventory_is_used_and_report_is_advisory_by_default(self):
        # Exercise the complete CLI against two real temporary Git revisions.
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            shutil.copy2(
                ROOT / "scripts/check_public_api.py",
                root / "scripts/check_public_api.py",
            )
            (root / "small.py").write_text("def public(value):\n    return value\n")
            inventory = (
                '[callables]\npublic = "small:public"\n[constants]\n[attributes]\n'
            )
            (root / "scripts/public_api.toml").write_text(inventory)

            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", str(root), *args],
                    text=True,
                    env=os.environ | {"GIT_CONFIG_GLOBAL": os.devnull},
                ).strip()

            git("init", "-q")
            git("add", ".")
            git(
                "-c",
                "user.name=Invented Tester",
                "-c",
                "user.email=example@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "baseline",
            )
            base = git("rev-parse", "HEAD")
            (root / "scripts/public_api.toml").write_text(
                "[callables]\n[constants]\n[attributes]\n"
            )
            command = [
                sys.executable,
                str(root / "scripts/check_public_api.py"),
                "--base",
                base,
                "--output",
                str(root / "report"),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("public: documented callable missing", result.stdout)
            self.assertEqual(
                subprocess.run(
                    [*command, "--fail-on-change"], capture_output=True
                ).returncode,
                1,
            )
            self.assertIn(
                "public",
                json.loads((root / "report/base.json").read_text())["callables"],
            )
            git("add", "scripts/public_api.toml")
            git(
                "-c",
                "user.name=Invented Tester",
                "-c",
                "user.email=example@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "candidate",
            )
            candidate = git("rev-parse", "HEAD")
            named = subprocess.run(
                [*command, "--candidate", candidate], capture_output=True, text=True
            )
            self.assertEqual(named.returncode, 0, named.stderr)
            self.assertIn(candidate, named.stdout)
            self.assertIn("public: documented callable missing", named.stdout)
            failed = subprocess.run(
                [*command[:3], "does-not-exist", *command[4:]],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(
                "No compatibility verdict", (root / "report/summary.md").read_text()
            )


if __name__ == "__main__":
    unittest.main()
