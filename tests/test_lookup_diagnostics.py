# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Lookup diagnostics identify the affected record and a concrete repair."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from attrs import fields

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.doi import order_doi_urls
from analysis_lister.glance.paper import Paper
from analysis_lister.markdown.subgroup_pages.published import render_paper_block


class LookupDiagnosticsTests(unittest.TestCase):
    def paper(self, urls):
        data = {field.name: "" for field in fields(Paper) if field.init}
        data.update(
            ref_code="TOPQ-2099-01",
            status=" Phase 0 is  Finished ",
            status_paper=" Publication Phase is  Active ",
            date_publication="2025-01-01",
            doi_urls=urls,
            keywords=[],
            subgroups=[],
            supporting_docs=[],
            title_short="GLANCE fallback",
        )
        return Paper.from_json(data)

    def test_missing_journal_references_identify_article_and_correction(self):
        dois = ["10.1007/JHEP01(2024)999", "10.1007/JHEP01(2025)999"]
        with (
            patch.dict("analysis_lister.citation_store.Citations", {}, clear=True),
            self.assertLogs(level="WARNING") as logs,
        ):
            paper = self.paper([f"https://doi.org/{doi}" for doi in dois])
        self.assertEqual(len(logs.output), 2)
        for message, doi, role in zip(
            logs.output, dois, ("original article", "correction"), strict=True
        ):
            for expected in ("TOPQ-2099-01", doi, role, "json/doi_metadata.json"):
                self.assertIn(expected, message)
        self.assertEqual(paper.journal_ref, "")
        self.assertEqual(paper.journal_ref_corrections, [""])

    def test_glance_title_is_rendered_without_lookup_warnings(self):
        paper = self.paper([])
        with self.assertNoLogs(level="WARNING"):
            rendered = render_paper_block(paper, attribute_tag=False)
        self.assertIn("TOPQ-2099-01 – GLANCE fallback", rendered)

    def test_ambiguous_order_warning_points_to_citation_metadata(self):
        urls = [
            "https://doi.org/10.9999/synthetic-a",
            "https://doi.org/10.9999/synthetic-b",
        ]
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(order_doi_urls(urls, "DEMO-2099-01"), urls)
        self.assertIn("json/doi_metadata.json", logs.output[0])


if __name__ == "__main__":
    unittest.main()
