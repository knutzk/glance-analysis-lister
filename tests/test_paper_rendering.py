# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Paper archive rows, citations, dates and expandable details."""

import json
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import (
    papers_page,
    pubnotes_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[1]


class PaperRenderingTests(unittest.TestCase):
    def prepare(self, data, group="DEMO", **options):
        return prepare_group(CuratedRegistry(data), GroupProfile(group, **options))

    def test_paper_board_marks_recorded_chairs_without_duplicates(self):
        for chairs in ([], ["Invented Chair", "Separate Chair", "Invented Chair"]):
            with self.subTest(chairs=chairs):
                paper = publication(1)
                paper["phase1"] = {
                    "gal_editorialBoard": [
                        "Invented Member",
                        "Invented Chair",
                        "Invented Member",
                    ],
                    "gal_editorialBoardChairs": chairs,
                }
                view = self.prepare(snapshot(analysis(1), papers=(paper,)))
                row = next(row for row in view.archive if row.resource == "papers")
                self.assertEqual(row.details.board_chairs, tuple(chairs))
                self.assertEqual(
                    row.provenance["details"]["inputs"][
                        "phase1.gal_editorialBoardChairs"
                    ],
                    chairs,
                )
                page = BeautifulSoup(papers_page(view), "html.parser").get_text(
                    " ", strip=True
                )
                expected = "Invented Member, Invented Chair"
                if chairs:
                    expected += " (chair), Separate Chair (chair)"
                self.assertIn(expected, page)
                self.assertEqual(page.count("Invented Chair (chair)"), bool(chairs))
                self.assertNotIn("Invented Member (chair)", page)

    def test_archive_selects_outputs_across_all_years_and_uses_publication_dates(self):
        old = publication(1, date="1999-01-01")
        submitted = publication(2, status="Publication Phase Active", date=None)
        submitted["publicationPhase"]["arXivSubmissionDate"] = "2099-03-01T12:00:00Z"
        active = publication(3, status="Phase 2 Active", date=None)
        missing_date = publication(4, date=None)
        note = publication(5, resource="confnotes", status="Phase 1 Finished")
        note["supersededBy"] = [
            {"type": "Paper", "referenceCode": old["referenceCode"]}
        ]
        view = self.prepare(
            snapshot(
                analysis(1),
                papers=(old, submitted, active, missing_date),
                confnotes=(note,),
            )
        )
        self.assertEqual(len(view.archive), 4)
        self.assertEqual(view.archive[0].reference, note["temporaryReferenceCode"])
        self.assertIsNone(
            next(
                row.date
                for row in view.archive
                if row.reference == submitted["referenceCode"]
            )
        )
        self.assertIsNone(view.archive[-1].date)
        self.assertIn(old["referenceCode"], {row.reference for row in view.archive})
        self.assertIn(
            note["temporaryReferenceCode"], {row.reference for row in view.archive}
        )
        trace = next(
            item
            for item in view.decisions
            if item["resource"] == "papers"
            and item["reference"] == active["referenceCode"]
        )
        self.assertFalse(trace["archive_inclusion"]["value"])
        trace = next(
            item
            for item in view.decisions
            if item["resource"] == "papers"
            and item["reference"] == submitted["referenceCode"]
        )
        self.assertIn("publicationPhase.publishedOnlineDate", trace["date"]["inputs"])

    def test_paper_details_show_latest_milestone_and_submission_date(self):
        paper = publication(1, status="Publication Phase Active", date=None)
        paper["publicationPhase"].update(
            {
                "arXivSubmissionDate": "2099-03-01T12:00:00Z",
                "startDate": "2099-02-01",
            }
        )
        view = self.prepare(snapshot(analysis(1), papers=(paper,)))
        soup = BeautifulSoup(papers_page(view), "html.parser")
        self.assertIn(
            "Submission · arXiv submission · 2099-03-01",
            soup.select_one("[data-gal-paper-details]").text,
        )
        paper["publicationPhase"]["journalAcceptanceDate"] = "2099-04-01"
        view = self.prepare(snapshot(analysis(1), papers=(paper,)))
        self.assertEqual(
            view.archive[0].details.last_milestone,
            ("Submission · Journal acceptance", "2099-04-01"),
        )

    def test_paper_record_buttons_preserve_citation_doi_pairs(self):
        paper = publication(1)
        paper["publicationPhase"]["arXivUrls"] = [
            {"url": "https://example.test/preprint"}
        ]
        paper["publicationPhase"]["gal_dois"] = [
            {"doi": "10.9999/original", "citation": "Invented journal citation"},
            {
                "doi": "10.9999/correction",
                "citation": "Invented correction",
                "url": "https://example.test/correction",
            },
        ]
        view = self.prepare(snapshot(analysis(1), papers=(paper,)))
        soup = BeautifulSoup(papers_page(view), "html.parser")
        links = soup.select(".gal-publication-records a")
        self.assertEqual(
            [(link.text, link["href"]) for link in links],
            [
                ("arXiv", "https://example.test/preprint"),
                ("Invented journal citation", "https://doi.org/10.9999/original"),
                ("Invented correction", "https://example.test/correction"),
            ],
        )
        self.assertEqual(
            soup.select_one("[data-gal-item] th a").text, paper["referenceCode"]
        )
        details = soup.select_one("[data-gal-paper-details]")
        self.assertFalse(details.has_attr("hidden"))
        self.assertIsNotNone(details.select_one("[data-gal-paper-collapse]"))

    def test_archive_html_keeps_full_table_and_inherited_subgroup_evidence(self):
        value = analysis(1)
        paper = publication(1, group=None, related=value["referenceCode"])
        paper["gal_contactEditors"] = ["Invented Editor"]
        paper["phase1"] = {"gal_editorialBoard": ["Invented Board Member"]}
        paper["publicationPhase"]["arXivUrls"] = [{"url": "https://example.test/arxiv"}]
        paper["shortTitle"] = 'Invented <script> "quoted" | title'
        paper["publicationPhase"]["gal_dois"][0]["citation"] = (
            "Synthetic <citation> | text"
        )
        note = publication(2, resource="pubnotes", status="Phase 1 Finished", date=None)
        view = self.prepare(snapshot(value, papers=(paper,), pubnotes=(note,)))
        markup = papers_page(view)
        soup = BeautifulSoup(markup, "html.parser")
        rows = soup.select("tbody [data-gal-item]")
        self.assertEqual(
            len(rows), sum(row.resource == "papers" for row in view.archive)
        )
        self.assertTrue(all(not row.has_attr("hidden") for row in rows))
        self.assertTrue(soup.select_one("[data-gal-controls]").has_attr("hidden"))
        self.assertEqual(len(soup.select("thead th[scope=col]")), 4)
        detail = rows[0].find_next_sibling("tr")
        self.assertEqual(detail.td["colspan"], "4")
        self.assertFalse(soup.find_all("script"))
        self.assertIn('Invented <script> "quoted" | title', rows[0].get_text())
        self.assertIn("Synthetic <citation> | text", rows[0].get_text())
        self.assertNotIn(
            "Synthetic <citation> | text",
            detail.select_one(".gal-publication-details__body").get_text(),
        )
        self.assertIsNotNone(rows[0].select_one("[data-gal-paper-toggle]"))
        self.assertIn(
            "Invented Editor",
            detail.select_one(".gal-publication-details__body").get_text(),
        )
        self.assertIn(
            "Invented Board Member",
            detail.select_one(".gal-publication-details__body").get_text(),
        )
        self.assertIsNotNone(rows[0].select_one('a[href="https://example.test/arxiv"]'))
        note_row = BeautifulSoup(pubnotes_page(view), "html.parser").select_one(
            "tbody tr"
        )
        self.assertIsNotNone(
            note_row.find_next_sibling("tr").select_one(".gal-badge--leading")
        )

        self.assertIn("Via linked analysis", detail.get_text())
        metadata = json.loads(rows[0]["data-gal-metadata"])
        self.assertEqual(set(metadata), {"text", "publication_status"})
        self.assertIn("Example subgroup, with comma", metadata["text"])
        self.assertIn(
            "inherited", view.archive[0].provenance["leading_subgroup"]["reason"]
        )
        self.assertFalse(soup.select('[data-gal-filter="subgroups"]'))
        self.assertIsNone(soup.select_one('[data-gal-filter="leading_subgroup"]'))
        self.assertIsNone(soup.select_one('[data-gal-filter="keywords"]'))
        self.assertNotIn("Not recorded", note_row.get_text())
        self.assertIsNone(note_row.select_one(".gal-native-id"))
        self.assertFalse(
            detail.select_one(".gal-publication-details__body").has_attr("open")
        )
        self.assertNotIn("data-gal-pagination", markup)

        empty = BeautifulSoup(
            papers_page(self.prepare(snapshot(analysis(1)))), "html.parser"
        )
        self.assertEqual(len(empty.select("tbody tr")), 0)

    def test_recorded_metadata_is_visible_without_archive_dropdowns(self):
        paper = publication(1)
        paper["gal_groups"]["leadingSubgroup"] = "Leading assignment"
        paper["gal_groups"]["subgroups"] = ["Additional assignment"]
        paper["metadata"] = {"gal_keywords": ["Synthetic keyword", "A, B"]}
        view = self.prepare(snapshot(analysis(1), papers=(paper,)))
        soup = BeautifulSoup(papers_page(view), "html.parser")
        self.assertFalse(soup.select('[data-gal-filter="leading_subgroup"]'))
        self.assertFalse(soup.select(".gal-multiselect"))
        self.assertIn("Synthetic keyword", soup.select_one("tbody").text)
        self.assertIn("Additional assignment", soup.select_one("tbody").get_text())
        self.assertEqual(
            view.archive[0].metadata["leading_subgroup"], "Leading assignment"
        )


if __name__ == "__main__":
    unittest.main()
