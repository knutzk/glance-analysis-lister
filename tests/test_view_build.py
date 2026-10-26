# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Page generation, reports, output safeguards and import boundaries."""

import json
import subprocess
import sys
import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from view_fixtures import analysis, snapshot

from analysis_lister import cli
from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.build import render_group
from analysis_lister.views.markdown.links import external
from analysis_lister.views.markdown.pages import (
    ongoing_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[1]


class BuildTests(unittest.TestCase):
    def prepare(self, data, group="DEMO", **options):
        return prepare_group(CuratedRegistry(data), GroupProfile(group, **options))

    def test_counts_tables_escaping_and_local_links_share_the_prepared_collection(self):
        data = snapshot(
            analysis(1),
            analysis(2, group="OTHER", additional=("DEMO",)),
            analysis(3, status="Closed"),
        )
        view = self.prepare(data)
        ongoing = ongoing_page(view)
        self.assertEqual(
            BeautifulSoup(ongoing, "html.parser").select_one("[data-gal-count]").text,
            "2 analyses",
        )
        self.assertNotIn("<tag>", ongoing)
        soup = BeautifulSoup(ongoing, "html.parser")
        cards = soup.select("article[data-gal-item]")
        self.assertEqual(len(cards), 2)
        self.assertIn("Invented | title [link] <tag>", cards[0].get_text())
        self.assertFalse(soup.find_all("script"))
        self.assertTrue(soup.select_one("[data-gal-controls]").has_attr("hidden"))
        self.assertTrue(all(not card.has_attr("hidden") for card in cards))
        metadata = json.loads(cards[0]["data-gal-metadata"])
        self.assertEqual(metadata["subgroups"], ["Example subgroup, with comma"])
        self.assertEqual(
            set(metadata), {"text", "subgroups", "stage_order", "reference"}
        )
        for button in soup.select("[data-gal-value]"):
            self.assertEqual(button["type"], "button")
            self.assertEqual(button["aria-pressed"], "false")
        self.assertEqual(soup.select_one("[data-gal-count]")["aria-live"], "polite")
        self.assertIn("ref_code=ANA-DEMO-2099-01", ongoing)
        self.assertIn('id="analysis-demo-ana-demo-2099-01"', ongoing)
        self.assertNotIn("ANA-DEMO-2099-03", ongoing)
        self.assertEqual(external("Example", "javascript:alert(1)"), "Example")
        self.assertEqual(external("Example", "https://[invalid"), "Example")
        empty = self.prepare(snapshot(analysis(1, status="Closed")))
        self.assertIn("No analyses currently meet", ongoing_page(empty))

    def test_command_writes_pages_assets_and_hashed_report_without_touching_input(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path, output = root / "curated.json", root / "pages"
            path.write_text(json.dumps(snapshot(analysis(1))))
            before = path.read_bytes()
            cli.main(
                [
                    "render-group",
                    "--group",
                    "DEMO",
                    "--snapshot",
                    str(path),
                    "--output-dir",
                    str(output),
                ]
            )
            report = json.loads((output / "view-report.json").read_text())
            self.assertEqual(report["snapshot"]["sha256"], sha256(before).hexdigest())
            self.assertEqual(report["counts"]["ongoing_analyses"], 1)
            self.assertEqual(len(report["decisions"]), 1)
            self.assertEqual(
                report["report_scope"]["other_records_omitted"]["papers"], 1
            )
            self.assertEqual(
                {p.name for p in output.iterdir()},
                {
                    "ongoing.md",
                    "papers.md",
                    "confnotes.md",
                    "pubnotes.md",
                    "view-report.json",
                    "assets",
                },
            )
            self.assertEqual(path.read_bytes(), before)
            generated = {
                str(p.relative_to(output)): p.read_bytes()
                for p in output.rglob("*")
                if p.is_file()
            }
            render_group(path, output, GroupProfile("DEMO"))
            self.assertEqual(
                generated,
                {
                    str(p.relative_to(output)): p.read_bytes()
                    for p in output.rglob("*")
                    if p.is_file()
                },
            )

            collision = root / "papers.md"
            collision.write_bytes(before)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                render_group(collision, root, GroupProfile("DEMO"))
            self.assertEqual(collision.read_bytes(), before)
            with self.assertRaises(ValueError):
                GroupProfile("")

    def test_new_views_do_not_import_legacy_or_network_clients(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "curated.json"
            path.write_text(json.dumps(snapshot(analysis(1))))
            code = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".")
               for name in ("analysis_lister.glance", "analysis_lister.markdown",
                            "analysis_lister.download", "stare", "selenium")):
            raise AssertionError("Forbidden dependency: " + fullname)
sys.meta_path.insert(0, Block())
from analysis_lister.views.build import render_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy
render_group(sys.argv[1], sys.argv[2], GroupProfile("DEMO"))
assert "requests" not in sys.modules
"""
            subprocess.run(
                [sys.executable, "-c", code, str(path), str(Path(directory) / "pages")],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
