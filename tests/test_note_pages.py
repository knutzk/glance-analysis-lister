# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Protect shared note-table formatting and the two distinct page introductions."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.confnote import ConfNote
from analysis_lister.glance.field_maps import REQUIRED_COLUMNS_ANALYSIS
from analysis_lister.glance.pubnote import PubNote
from analysis_lister.markdown.global_pages.confnotes import confnotes
from analysis_lister.markdown.global_pages.pubnotes import pubnotes


class NotePageTests(unittest.TestCase):
    def test_both_pages_preserve_links_escaping_order_and_distinct_text(self):
        for cls, render, filename, heading, identifier, date_column, exclusion in (
            (
                ConfNote,
                confnotes,
                "confnotes.md",
                "Conference notes",
                "ATLAS-CONF-2025-001",
                "Second Sign Off Date",
                "analysis has been closed, are not listed.",
            ),
            (
                PubNote,
                pubnotes,
                "pubnotes.md",
                "PUB notes",
                "ATL-PHYS-PUB-2025-001",
                "Second Reader Sign Off Date",
                "analysis has been closed or never started, are not listed.",
            ),
        ):
            with self.subTest(kind=cls.__name__), TemporaryDirectory() as directory:
                notes = []
                for ref in ("TOPQ-2025-02", "TOPQ-2025-01"):
                    row = dict.fromkeys(REQUIRED_COLUMNS_ANALYSIS, "")
                    row.update(
                        {
                            "Reference Code": ref,
                            "Status": " Phase 0 is  Finished ",
                            "Short Title": "Title | with delimiter",
                            "Subgroups": "TOPQ - Cross-section,TOPQ - Top Properties and Mass",
                        }
                    )
                    notes.append(
                        cls.from_analysis_and_dict(
                            Analysis.from_csv_dict(row),
                            {
                                "Reference Code": f" {identifier} ",
                                "Final URL": "https://example.test/note",
                                date_column: "2025-01-02",
                                "Status": " Phase 1 is  Active ",
                            },
                        )
                    )
                render(notes, Path(directory), "test sync")
                page = (Path(directory) / filename).read_text()
                self.assertIn(f"# {heading}\n", page)
                self.assertIn(exclusion, page)
                self.assertIn("test sync", page)
                self.assertEqual(
                    page.count("| Identifier | Analysis | Title | Subgroup | Date |"), 1
                )
                for ref in ("TOPQ-2025-02", "TOPQ-2025-01"):
                    self.assertIn(
                        f"| [{identifier.replace('-', '&#8209;')}](https://example.test/note) "
                        f"| {ref.replace('-', '&#8209;')} | Title / with delimiter "
                        "| XS, PM | 2025&#8209;01&#8209;02 |\n",
                        page,
                    )
                self.assertLess(
                    page.index("2025&#8209;02"), page.index("2025&#8209;01 |")
                )

    def test_empty_pages_keep_the_table_header(self):
        for render, filename in (
            (confnotes, "confnotes.md"),
            (pubnotes, "pubnotes.md"),
        ):
            with self.subTest(filename=filename), TemporaryDirectory() as directory:
                render([], Path(directory), "test sync")
                page = (Path(directory) / filename).read_text()
                self.assertIn("lists the 0", page)
                self.assertTrue(page.endswith("| --- | --- | --- | --- | --- |\n"))


if __name__ == "__main__":
    unittest.main()
