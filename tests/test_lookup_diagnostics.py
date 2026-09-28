"""Lookup diagnostics identify the affected record and a concrete repair."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from attrs import fields

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.doi import order_doi_urls
from analysis_lister.glance.paper import Paper
from analysis_lister.lookup_dicts.doi_order import DoiOrder
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
            patch.dict(
                "analysis_lister.glance.paper.journal_refs.JournalRefs", {}, clear=True
            ),
            self.assertLogs(level="WARNING") as logs,
        ):
            paper = self.paper([f"https://doi.org/{doi}" for doi in dois])
        self.assertEqual(len(logs.output), 2)
        for message, doi, role in zip(
            logs.output, dois, ("original article", "correction"), strict=True
        ):
            for expected in ("TOPQ-2099-01", doi, role, "lookup_dicts/journal_refs.py"):
                self.assertIn(expected, message)
        self.assertEqual(paper.journal_ref, "")
        self.assertEqual(paper.journal_ref_corrections, [""])

    def test_title_warning_identifies_fallback_and_edit_location(self):
        paper = self.paper([])
        with self.assertLogs(level="WARNING") as logs:
            rendered = render_paper_block(paper, attribute_tag=False)
        self.assertEqual(len(logs.output), 1)
        for expected in (
            paper.ref_code,
            "lookup_dicts/short_titles.py",
            "GLANCE fallback",
        ):
            self.assertIn(expected, logs.output[0])
        self.assertIn("TOPQ-2099-01 – GLANCE fallback", rendered)

    def test_stale_override_lists_missing_and_obsolete_dois(self):
        with (
            patch.dict(DoiOrder, {"TOPQ-2099-01": ["10.1007/obsolete"]}),
            self.assertRaises(ValueError) as error,
        ):
            order_doi_urls(["https://doi.org/10.1007/new"], "TOPQ-2099-01")
        message = str(error.exception)
        for expected in (
            "TOPQ-2099-01",
            "lookup_dicts/doi_order.py",
            "Missing from override: ['10.1007/new']",
            "absent from record: ['10.1007/obsolete']",
        ):
            self.assertIn(expected, message)


if __name__ == "__main__":
    unittest.main()
