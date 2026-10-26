# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""DOI ambiguity, automatic ordering, and citation alignment regressions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.citations.ordering import order_doi_urls

ORIGINAL = "10.1140/epjc/s10052-024-11111-1"
CORRECTION = "10.1140/epjc/s10052-024-99999-9"


class DoiOrderTests(unittest.TestCase):
    def test_cached_material_orders_correction_before_date_inference(self):
        citations = {
            ORIGINAL: {"material": "publication"},
            CORRECTION: {"material": "erratum"},
        }
        with self.assertNoLogs(level="WARNING"):
            self.assertEqual(
                order_doi_urls(
                    self.urls(CORRECTION, ORIGINAL), "TEST", citations=citations
                ),
                self.urls(ORIGINAL, CORRECTION),
            )

    def urls(self, *dois):
        return [f"https://doi.org/{doi}" for doi in dois]

    def test_multiple_known_corrections_keep_ambiguous_relative_order(self):
        second = "10.9999/invented-correction"
        citations = {
            ORIGINAL: {"material": "publication"},
            CORRECTION: {"material": "erratum"},
            second: {"material": "erratum"},
        }
        with self.assertNoLogs(level="WARNING"):
            self.assertEqual(
                order_doi_urls(
                    self.urls(second, ORIGINAL, CORRECTION), "TEST", citations=citations
                ),
                self.urls(ORIGINAL, second, CORRECTION),
            )

    def test_known_corrections_sort_by_distinct_dates(self):
        early = "10.1007/jhep01(2099)001"
        late = "10.1007/jhep03(2099)002"
        for material in ("erratum", "addendum", "editorial note"):
            citations = {
                ORIGINAL: {"material": "publication"},
                early: {"material": material},
                late: {"material": "erratum"},
            }
            with self.subTest(material=material), self.assertNoLogs(level="WARNING"):
                self.assertEqual(
                    order_doi_urls(
                        self.urls(late, early, ORIGINAL), "TEST", citations=citations
                    ),
                    self.urls(ORIGINAL, early, late),
                )

    def test_unknown_or_multiple_publications_still_warn(self):
        third = "10.9999/invented"
        for material in (None, "unknown", "publication"):
            citations = {
                ORIGINAL: {"material": "publication"},
                CORRECTION: {"material": "erratum"},
                third: {"material": material},
            }
            urls = self.urls(CORRECTION, third, ORIGINAL)
            with self.subTest(material=material), self.assertLogs(level="WARNING"):
                self.assertEqual(
                    order_doi_urls(urls, "TEST", citations=citations), urls
                )

    def test_distinct_dates_sort_and_host_aliases_deduplicate(self):
        original = "10.1007/JHEP07(2023)203"
        correction = "10.1007/JHEP05(2025)159"
        self.assertEqual(
            order_doi_urls(
                self.urls(correction, original) + [f"https://dx.doi.org/{original}"],
                "TEST",
            ),
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


if __name__ == "__main__":
    unittest.main()
