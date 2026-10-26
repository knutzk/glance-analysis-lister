# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Shared publication search and distinct archive pages."""

import json
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import (
    confnotes_page,
    ongoing_page,
    papers_page,
    pubnotes_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[1]


class PublicationRenderingTests(unittest.TestCase):
    def prepare(self, data, group="DEMO", **options):
        return prepare_group(CuratedRegistry(data), GroupProfile(group, **options))

    def test_all_archives_index_people_subgroups_keywords_and_publication_links(self):
        for resource in ("papers", "confnotes", "pubnotes"):
            record = publication(
                1,
                resource=resource,
                status="Publication Phase Finished"
                if resource == "papers"
                else "Phase 1 Finished",
            )
            record["gal_contactEditors"] = ["Invented Editor"]
            record["gal_groups"]["subgroups"] = ["DEMO-Searchable"]
            record["metadata"] = {"gal_keywords": ["Invented keyword"]}
            record.setdefault("phase1", {}).update(
                {
                    "gal_readers": ["Invented Reader"],
                    "draftCdsUrl": "https://cds.cern.ch/record/209900000001",
                }
            )
            view = self.prepare(snapshot(analysis(1), **{resource: (record,)}))
            row = next(row for row in view.archive if row.resource == resource)
            for value in (
                row.reference,
                row.label,
                row.title,
                "Invented Editor",
                "DEMO-Searchable",
                "Invented keyword",
            ):
                self.assertIn(value, row.metadata["text"])
            if resource == "papers":
                self.assertIn("10.9999/synthetic", row.metadata["text"])
                self.assertIn("Synthetic citation", row.metadata["text"])
            else:
                self.assertIn(
                    "https://cds.cern.ch/record/209900000001",
                    row.metadata["text"],
                )
                self.assertIn("Invented Reader", row.metadata["text"])
                soup = BeautifulSoup(
                    (confnotes_page if resource == "confnotes" else pubnotes_page)(
                        view
                    ),
                    "html.parser",
                )
                self.assertIn(
                    "Invented Editor",
                    soup.select_one("[data-gal-search-text]")["data-gal-search-text"],
                )
                self.assertFalse(soup.select('[data-gal-filter="subgroups"]'))

    def test_archive_month_controls_use_publication_dates_and_are_isolated(self):
        view = self.prepare(
            snapshot(
                analysis(1),
                papers=(publication(1, date="2099-04-17"),),
                confnotes=(
                    publication(
                        2,
                        resource="confnotes",
                        status="Phase 1 Finished",
                        date="2099-05-19",
                    ),
                ),
                pubnotes=(
                    publication(
                        3, resource="pubnotes", status="Phase 1 Finished", date=None
                    ),
                ),
            )
        )
        for render, expected in (
            (papers_page, "2099-04-17"),
            (confnotes_page, "2099-05-19"),
            (pubnotes_page, ""),
        ):
            soup = BeautifulSoup(render(view), "html.parser")
            row = soup.select_one(".gal-publication-filter-row")
            self.assertIsNotNone(row.select_one("fieldset"))
            self.assertIsNotNone(row.select_one("[data-gal-archive-expand-all]"))
            self.assertLess(
                str(soup).index("data-gal-date-before"),
                str(soup).index('class="gal-publication-filter-row"'),
            )
            for bound in ("after", "before"):
                control = soup.select_one(f"[data-gal-date-{bound}]")
                self.assertEqual(control["type"], "month")
                self.assertIsNotNone(soup.find("label", attrs={"for": control["id"]}))
            self.assertEqual(
                soup.select_one("[data-gal-date]")["data-gal-date"], expected
            )
            self.assertEqual(
                soup.select_one("[data-gal-archive-expand-all]").text, "Expand all"
            )
        paper_markup = papers_page(view)
        self.assertLess(
            paper_markup.index("data-gal-date-after"),
            paper_markup.index('data-gal-filter="publication_status"'),
        )
        self.assertNotIn("data-gal-date-after", ongoing_page(view))
        self.assertNotIn("data-gal-archive-expand-all", ongoing_page(view))


class SeparatePublicationPageTests(unittest.TestCase):
    def test_resources_have_separate_pages_and_search_controls(self):
        view = prepare_group(
            CuratedRegistry(
                snapshot(
                    analysis(1),
                    papers=(publication(1),),
                    confnotes=(
                        publication(2, resource="confnotes", status="Phase 1 Finished"),
                    ),
                    pubnotes=(
                        publication(3, resource="pubnotes", status="Phase 1 Finished"),
                    ),
                )
            ),
            GroupProfile("DEMO"),
        )
        for resource, render in (
            ("papers", papers_page),
            ("confnotes", confnotes_page),
            ("pubnotes", pubnotes_page),
        ):
            soup = BeautifulSoup(render(view), "html.parser")
            rows = soup.select(
                "tbody tr:not([data-gal-note-details]):not([data-gal-paper-details])"
            )
            self.assertEqual(len(rows), 1)
            if resource == "confnotes":
                self.assertIn("ATLAS-CONF-2099-002", rows[0].get_text())
            elif resource == "pubnotes":
                self.assertIn("ATL-PHYS-PUB-2099-003", rows[0].get_text())
            else:
                self.assertEqual(
                    set(json.loads(rows[0]["data-gal-metadata"])),
                    {"text", "publication_status"},
                )
            self.assertEqual(
                bool(soup.select("[data-gal-archive]")), resource == "papers"
            )
            self.assertEqual(bool(soup.select("[data-gal-search]")), True)
            self.assertFalse(soup.select('[data-gal-filter="publication_type"]'))

    def test_publication_search_has_its_own_module_and_browser_entrypoint(self):
        from analysis_lister.views.markdown import (
            ongoing,
            ongoing_controls,
            papers,
            publication_controls,
        )

        self.assertIs(ongoing.render_controls, ongoing_controls.render_controls)
        self.assertIs(papers.render_controls, publication_controls.render_controls)
        self.assertIsNot(ongoing.render_controls, papers.render_controls)
        ongoing = (ROOT / "analysis_lister/views/assets/gal-ongoing.js").read_text()
        paper = (ROOT / "analysis_lister/views/assets/gal-papers.js").read_text()
        self.assertIn(".gal-ongoing[data-gal-collection]", ongoing)
        self.assertIn("window.GALPapers", paper)
        self.assertNotIn("window.GALOngoing", paper)


if __name__ == "__main__":
    unittest.main()
