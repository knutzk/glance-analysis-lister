# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Obsidian export uses explicit paths, private lookups and synthetic records."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister import cli
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.lookup_dicts.short_titles import ShortTitles
from analysis_lister.obsidian import export_obsidian, render_front_matter

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/synthetic_registry.json"
LOOKUPS = ROOT / "examples/lookups"


class ObsidianExportTests(unittest.TestCase):
    def test_cli_exports_example_and_reports_stale_notes_without_deleting(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "vault"
            published = output / "obs_published"
            published.mkdir(parents=True)
            stale = published / "user-note.md"
            stale.write_text("User content")
            with self.assertLogs(level="WARNING") as logs:
                cli.main(
                    [
                        "export-obsidian",
                        "--snapshot",
                        str(EXAMPLE),
                        "--output-dir",
                        str(output),
                        "--lookup-dir",
                        str(LOOKUPS),
                    ]
                )
            self.assertEqual(stale.read_text(), "User content")
            self.assertTrue(any("user-note.md" in log for log in logs.output))
            paper = published / "DEMO-2099-02-Synthetic-published-paper.md"
            ongoing = output / "obs_ongoing/DEMO-2099-01-Synthetic-ongoing-analysis.md"
            self.assertIn("Synthetic published paper", paper.read_text())
            self.assertIn("Synthetic ongoing analysis", ongoing.read_text())
            self.assertEqual(ShortTitles, {})

    def test_default_output_is_standalone_directory(self):
        with patch("analysis_lister.obsidian.export_obsidian") as export:
            cli.main(["export-obsidian", "--snapshot", str(EXAMPLE)])
        export.assert_called_once_with(EXAMPLE, Path("obsidian_output"))

    def test_missing_snapshot_does_not_create_output(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "notes"
            with self.assertRaises(OSError):
                export_obsidian(Path(directory) / "missing.json", output)
            self.assertFalse(output.exists())

    def test_front_matter_preserves_yaml_special_characters(self):
        entry = GlanceRegistry.from_json(EXAMPLE).get("DEMO-2099-01")
        entry.title_short = 'Title: "quoted" # with\na newline'
        with patch.dict(ShortTitles, {entry.ref_code: entry.title_short}):
            front_matter = render_front_matter(entry, entry.ref_code, "analysis")
        fields = dict(
            line.split(": ", 1)
            for line in front_matter.splitlines()
            if line.startswith(("title: ", "summary: "))
        )
        self.assertEqual(json.loads(fields["summary"]), entry.title_short)
        self.assertEqual(
            json.loads(fields["title"]), f"{entry.ref_code} – {entry.title_short}"
        )

    def test_import_does_not_configure_logging(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import logging
from unittest.mock import patch
with patch.object(logging, "basicConfig", side_effect=AssertionError("logging")):
    import analysis_lister.obsidian
""",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_missing_snapshot_exits_without_traceback(self):
        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "analysis_lists.py"), "export-obsidian"],
                cwd=directory,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)


class SyntheticExampleTests(unittest.TestCase):
    def test_example_covers_all_models_and_uses_demo_identifiers(self):
        registry = GlanceRegistry.from_json(EXAMPLE)
        self.assertEqual(
            {type(entry).__name__ for entry in registry.entries.values()},
            {"Analysis", "Paper", "ConfNote", "PubNote"},
        )
        self.assertEqual(len(registry.analyses), 1)
        self.assertEqual(len(registry.papers), 1)
        self.assertEqual(len(registry.confnotes), 1)
        self.assertEqual(len(registry.pubnotes), 1)
        self.assertTrue(all(ref.startswith("DEMO-2099-") for ref in registry.entries))

    def test_example_renders_all_site_pages_with_public_lookups(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "pages"
            cli.main(
                [
                    "render",
                    "--snapshot",
                    str(EXAMPLE),
                    "--output-dir",
                    str(output),
                    "--lookup-dir",
                    str(LOOKUPS),
                ]
            )
            self.assertEqual(len(list(output.rglob("*.md"))), 13)
            for name, title in (
                ("ongoing.md", "Synthetic ongoing analysis"),
                ("published.md", "Synthetic published paper"),
                ("confnotes.md", "Synthetic CONF note"),
                ("pubnotes.md", "Synthetic PUB note"),
            ):
                self.assertIn(title, (output / name).read_text())
