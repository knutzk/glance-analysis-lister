# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Page introductions and offline report output."""

import io
import json
import unittest
from contextlib import redirect_stdout
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup

from analysis_lister import cli
from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import archive_curation_intro
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy


class PageOutputTests(unittest.TestCase):
    def test_report_is_announced_on_stdout_but_not_linked_from_pages(self):
        snapshot = (
            Path(__file__).resolve().parents[1] / "examples/synthetic_registry.json"
        )
        with TemporaryDirectory() as directory:
            output = Path(directory)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                cli.main(
                    [
                        "render-group",
                        "--group",
                        "DEMO",
                        "--snapshot",
                        str(snapshot),
                        "--output-dir",
                        str(output),
                    ]
                )
            self.assertTrue((output / "view-report.json").is_file())
            self.assertFalse((output / "index.md").exists())
            self.assertFalse((output / "publications.md").exists())
            self.assertEqual(len(list(output.glob("*.md"))), 4)
            self.assertIn(str(output / "view-report.json"), stdout.getvalue())
            report = json.loads((output / "view-report.json").read_text())
            for page in output.glob("*.md"):
                content = page.read_text()
                self.assertTrue(content.startswith("---\nhide:\n  - toc\n---\n\n<!--"))
                self.assertIn(
                    "Generator Git commit: " + report["generator"]["git_commit"],
                    content,
                )
                self.assertIn("Registry snapshot: synthetic_registry.json", content)
                self.assertIn(
                    "Registry SHA-256: " + sha256(snapshot.read_bytes()).hexdigest(),
                    content,
                )
                self.assertNotIn("Curated registry built:", content)
                self.assertIn("GLANCE data extracted:", content)
                self.assertIn("Generated with [glance-analysis-lister]", content)
                revision = report["generator"]["git_commit"]
                if revision != "unknown":
                    self.assertIn("/commit/" + revision.removesuffix("-dirty"), content)
                self.assertNotIn("view-report.json", page.read_text())
                self.assertNotIn("[Group overview]", page.read_text())
                if page.name != "ongoing.md":
                    scope = BeautifulSoup(page.read_text(), "html.parser").select_one(
                        ".gal-archive-scope"
                    )
                    self.assertIsNotNone(scope)
                    self.assertIn("spearheaded by DEMO", scope.get_text())
                self.assertNotIn(
                    "Derivation rules and source evidence", page.read_text()
                )

    def test_scope_uses_group_token_and_contains_all_configured_criteria(self):
        registry = CuratedRegistry.from_json(
            Path(__file__).resolve().parents[1] / "examples/synthetic_registry.json"
        )
        policy = PublicationPolicy(
            title="Display title",
            groups=("DEMO", "OLD"),
            subgroups=("OTHER-Merged",),
            keywords=("Invented topic",),
        )
        view = prepare_group(registry, GroupProfile("DEMO", publication_policy=policy))
        scope = BeautifulSoup(archive_curation_intro(view), "html.parser").select_one(
            ".gal-archive-scope"
        )
        self.assertIn("spearheaded by DEMO", scope.get_text())
        self.assertNotIn("Display title", scope.get_text())
        self.assertIn("ANY listed criterion", scope.get_text())
        self.assertEqual(
            [node.get_text() for node in scope.select("code")],
            ["DEMO", "OLD", "OTHER-Merged", "Invented topic"],
        )
