# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Table source keeps each data and expansion row independently diffable."""

import json
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.layout import metadata_json, readable_html
from analysis_lister.views.markdown.notes import note_table
from analysis_lister.views.markdown.papers import paper_table
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy


class TableLayoutTests(unittest.TestCase):
    def test_compact_cells_and_detail_fields_have_separate_lines(self):
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
                self.assertTrue(
                    any(
                        line.startswith('<th scope="row"') and line.endswith("</tr>")
                        for line in markup.splitlines()
                    )
                )
                self.assertTrue(
                    any(
                        line.startswith("<dt>") and "</dt><dd>" in line
                        for line in markup.splitlines()
                    )
                )
                self.assertNotIn("\n\n", markup.strip())
                soup = BeautifulSoup(markup, "html.parser")
                body_rows = soup.select("tbody > tr")
                self.assertEqual(len(body_rows), 2)
                self.assertIs(body_rows[0].find_next_sibling(), body_rows[1])
                self.assertFalse(
                    soup.select("[data-gal-subgroups], [data-gal-resource]")
                )
                if resource == "papers":
                    self.assertEqual(
                        set(json.loads(body_rows[0]["data-gal-metadata"])),
                        {"text", "publication_status"},
                    )
                else:
                    self.assertIn("data-gal-search-text", body_rows[0].attrs)
                    self.assertIn("data-gal-date", body_rows[0].attrs)
                    self.assertIn("data-gal-superseded", body_rows[0].attrs)

    def test_layout_preserves_elements_attributes_and_inline_content(self):
        source = '<section><div><a href="https://example.test">A <strong>linked</strong> label</a></div><dl><dt>Editors</dt><dd>First, Second</dd></dl><table><tbody><tr data-gal-item><td>Compact</td><td>Row</td></tr><tr class="gal-paper-detail-row"><td><div><p>Details</p></div></td></tr></tbody></table></section>'
        formatted = readable_html(source)
        original, result = (
            BeautifulSoup(value, "html.parser") for value in (source, formatted)
        )
        self.assertEqual(
            [(tag.name, tag.attrs) for tag in original.find_all()],
            [(tag.name, tag.attrs) for tag in result.find_all()],
        )
        self.assertEqual(
            original.get_text(" ", strip=True), result.get_text(" ", strip=True)
        )
        self.assertEqual(str(original.a), str(result.a))

    def test_json_metadata_is_stable_and_decodes_after_html_parsing(self):
        values = {"text": 'A "quoted" <title>\nnext line', "keywords": ["B", "A"]}
        encoded = metadata_json(values)
        self.assertEqual(encoded, metadata_json(dict(reversed(list(values.items())))))
        html = BeautifulSoup(
            '<div data-gal-metadata="' + encoded + '"></div>', "html.parser"
        )
        self.assertEqual(json.loads(html.div["data-gal-metadata"]), values)
