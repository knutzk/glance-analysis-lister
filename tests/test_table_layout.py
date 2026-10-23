# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Table source keeps each data and expansion row independently diffable."""

import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.notes import note_table
from analysis_lister.views.markdown.papers import paper_table
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy


class TableLayoutTests(unittest.TestCase):
    def test_each_html_row_has_its_own_line(self):
        registry = CuratedRegistry.from_json(
            Path(__file__).resolve().parents[1] / "examples/synthetic_registry.json"
        )
        view = prepare_group(
            registry,
            GroupProfile(
                "DEMO", publication_policy=PublicationPolicy(groups=("DEMO",))
            ),
        )
        for resource, markup in (
            ("papers", paper_table(view)),
            ("confnotes", note_table(view, "confnotes")),
            ("pubnotes", note_table(view, "pubnotes")),
        ):
            with self.subTest(resource=resource):
                rows = [line for line in markup.splitlines() if line.startswith("<tr")]
                self.assertEqual(len(rows), 3)  # Header, publication, expansion.
                for row in rows:
                    self.assertEqual(row.count("<tr"), 1)
                    self.assertEqual(row.count("</tr>"), 1)
                    self.assertTrue(row.endswith("</tr>"))
                soup = BeautifulSoup(markup, "html.parser")
                body_rows = soup.select("tbody > tr")
                self.assertEqual(len(body_rows), 2)
                self.assertIs(body_rows[0].find_next_sibling(), body_rows[1])
