"""DOI ambiguity, explicit ordering, and citation alignment regressions."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from attrs import fields

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.doi import format_url_dois, order_doi_urls
from analysis_lister.glance.paper import Paper
from analysis_lister.lookup_dicts.doi_order import DoiOrder
from analysis_lister.markdown.subgroup_pages.published import render_citation_block

ORIGINAL = "10.1140/epjc/s10052-024-11111-1"
CORRECTION = "10.1140/epjc/s10052-024-99999-9"


class DoiOrderTests(unittest.TestCase):
    def urls(self, *dois):
        return [f"https://doi.org/{doi}" for doi in dois]

    def test_distinct_dates_sort_and_host_aliases_deduplicate(self):
        original = "10.1007/JHEP07(2023)203"
        correction = "10.1007/JHEP05(2025)159"
        raw = (
            "".join(self.urls(correction, original)) + f"https://dx.doi.org/{original}"
        )
        self.assertEqual(
            order_doi_urls(format_url_dois(raw), "TEST"),
            self.urls(original, correction),
        )

    def test_ambiguous_dates_preserve_input_and_warn(self):
        for dois in (
            [CORRECTION, ORIGINAL],
            ["10.1007/JHEP07(2023)203", "10.1007/JHEP07(2023)999"],
            ["10.1007/JHEP07(2024)203", ORIGINAL],
            ["10.1007/JHEP07(2024)203", "10.1103/PhysRevD.94.092003"],
        ):
            with self.subTest(dois=dois), self.assertLogs(level="WARNING") as logs:
                urls = self.urls(*dois)
                self.assertEqual(order_doi_urls(urls, "TOPQ-2025-01"), urls)
            self.assertIn("ambiguous DOI order", logs.output[0])

    def test_override_and_stale_override(self):
        with patch.dict(DoiOrder, {"TEST": [ORIGINAL, CORRECTION]}):
            self.assertEqual(
                order_doi_urls(self.urls(CORRECTION, ORIGINAL), "TEST"),
                self.urls(ORIGINAL, CORRECTION),
            )
            with self.assertRaisesRegex(ValueError, "override does not match"):
                order_doi_urls(self.urls(ORIGINAL), "TEST")
        with (
            patch.dict(DoiOrder, {"TEST": [ORIGINAL, ORIGINAL]}),
            self.assertRaises(ValueError),
        ):
            order_doi_urls(self.urls(ORIGINAL), "TEST")

    def test_json_load_applies_override_before_resolving_citations(self):
        data = {field.name: "" for field in fields(Paper) if field.init}
        data.update(
            ref_code="TEST",
            status=" Phase 0 is  Finished ",
            status_paper=" Publication Phase is  Active ",
            date_publication="2024-01-01",
            doi_urls=self.urls(CORRECTION, ORIGINAL),
            keywords=[],
            subgroups=[],
            supporting_docs=[],
            journal_ref="stale serialized citation",
        )
        with (
            patch.dict(DoiOrder, {"TEST": [ORIGINAL, CORRECTION]}),
            patch.dict(
                "analysis_lister.glance.paper.journal_refs.JournalRefs",
                {
                    ORIGINAL: "Original citation",
                    CORRECTION: "Erratum citation",
                },
            ),
        ):
            paper = Paper.from_json(data)
            base = Analysis.from_json(
                {
                    field.name: data.get(field.name, "")
                    for field in fields(Analysis)
                    if field.init
                }
            )
            from_csv = Paper.from_analysis_and_dict(
                base,
                {
                    "Final Journal Publication URLs": "".join(
                        self.urls(CORRECTION, ORIGINAL)
                    ),
                    "Status": " Publication Phase is  Active ",
                    "Publication Date": "2024-01-01",
                },
            )
        self.assertEqual(from_csv.dois, paper.dois)
        self.assertEqual(
            from_csv.journal_ref_corrections, paper.journal_ref_corrections
        )
        self.assertEqual(paper.dois, [ORIGINAL, CORRECTION])
        self.assertEqual(paper.journal_ref, "Original citation")
        self.assertEqual(paper.journal_ref_corrections, ["Erratum citation"])
        block = render_citation_block(paper)
        self.assertIn(f"[Erratum citation, DOI: {CORRECTION}]", block)
        self.assertLess(block.index(ORIGINAL), block.index(CORRECTION))


if __name__ == "__main__":
    unittest.main()
