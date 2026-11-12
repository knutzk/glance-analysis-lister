# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Restore v0.1 citation content using independently invented API records."""

import copy
import unittest

from attrs import evolve
from bs4 import BeautifulSoup
from view_fixtures import api_fixture, publication, snapshot

from grove.registry import CuratedRegistry
from grove.registry.enrichment import curate
from grove.views.markdown.pages import papers_page
from grove.views.models import PublicationDetails
from grove.views.paper_citations import arxiv_reference
from grove.views.prepare import prepare_group
from grove.views.profiles import GroupProfile


class PaperCitationTests(unittest.TestCase):
    def view(self, paper):
        return prepare_group(
            CuratedRegistry(snapshot(papers=(paper,))), GroupProfile("DEMO")
        )

    def test_complete_citation_preserves_tex_and_each_doi_pair(self):
        paper = publication(1)
        title = r'Invented $X \to Y$ <study> & "measurement"'
        paper["fullTitle"] = "Earlier full title"
        paper["publicationPhase"].update(
            finalTitleTex=title,
            arXivUrls=[{"url": "https://arxiv.org/abs/9901.12345v2"}],
            grove_dois=[
                {"doi": "10.9999/original", "citation": "Demo J. 12 (2099) 123"},
                {"doi": "10.9999/erratum", "citation": "Erratum: Demo J. 13 (2099) 5"},
                {"doi": "10.9999/unresolved"},
                {
                    "doi": "10.9999/addendum",
                    "citation": "Addendum: Demo J. 14 (2099) 6",
                },
            ],
        )
        before = copy.deepcopy(paper)
        view = self.view(paper)
        expected = (
            "ATLAS Collaboration",
            title,
            "Demo J. 12 (2099) 123, arXiv:9901.12345v2",
            "DOI: 10.9999/original",
            "[Erratum: Demo J. 13 (2099) 5, DOI: 10.9999/erratum]",
            "[DOI: 10.9999/unresolved]",
            "[Addendum: Demo J. 14 (2099) 6, DOI: 10.9999/addendum]",
        )
        self.assertEqual(view.archive[0].details.cite_as, expected)
        soup = BeautifulSoup(papers_page(view), "html.parser")
        block = soup.select_one(".grove-paper-citation")
        self.assertEqual(tuple(block.stripped_strings), expected)
        self.assertIsNone(block.find("study"))
        self.assertFalse(block.find_parent("tr").has_attr("hidden"))
        self.assertIn(title, view.archive[0].metadata["text"])
        self.assertIn("arXiv:9901.12345v2", view.archive[0].metadata["text"])
        self.assertEqual(paper, before)

    def test_submitted_paper_without_doi_uses_recorded_journal_and_arxiv(self):
        paper = publication(1, status="Publication Phase Active", date=None)
        paper["publicationPhase"].update(
            arXivSubmissionDate="2099-01-01",
            finalSubmissionJournal="NEW_JOURNAL_CODE",
            arXivUrls=[{"url": "https://arxiv.org/pdf/hep-ex/9901999.pdf"}],
            grove_dois=[],
        )
        self.assertEqual(
            self.view(paper).archive[0].details.cite_as,
            (
                "ATLAS Collaboration",
                "Synthetic publication",
                "Submitted to NEW_JOURNAL_CODE, arXiv:hep-ex/9901999",
            ),
        )

    def test_older_and_sparse_records_keep_available_information(self):
        paper = publication(1, date=None)
        paper["fullTitle"] = "Invented full title"
        paper["publicationPhase"] = None
        self.assertEqual(
            self.view(paper).archive[0].details.cite_as[1], paper["fullTitle"]
        )
        for empty in (None, ""):
            paper["fullTitle"] = empty
            paper["publicationPhase"] = {"finalTitleTex": empty}
            self.assertEqual(
                self.view(paper).archive[0].details.cite_as,
                ("ATLAS Collaboration", "Synthetic publication"),
            )
        del paper["fullTitle"]
        del paper["shortTitle"]
        self.assertEqual(
            self.view(paper).archive[0].details.cite_as,
            ("ATLAS Collaboration", paper["referenceCode"]),
        )

    def test_unresolved_original_does_not_borrow_a_correction_citation(self):
        paper = publication(1)
        paper["publicationPhase"]["grove_dois"] = [
            {"doi": "10.9999/unresolved"},
            {"doi": "10.9999/correction", "citation": "Invented correction"},
        ]
        self.assertEqual(
            self.view(paper).archive[0].details.cite_as[2:],
            (
                "DOI: 10.9999/unresolved",
                "[Invented correction, DOI: 10.9999/correction]",
            ),
        )

    def test_sparse_doi_entries_keep_available_references_without_empty_lines(self):
        paper = publication(1)
        paper["publicationPhase"]["grove_dois"] = [
            {"citation": "Invented original reference"},
            {},
            {"citation": "Invented correction reference", "doi": None},
            {"url": "https://doi.org/10.9999/addendum"},
        ]
        view = self.view(paper)
        expected = (
            "ATLAS Collaboration",
            "Synthetic publication",
            "Invented original reference",
            "[Invented correction reference]",
            "[DOI: https://doi.org/10.9999/addendum]",
        )
        self.assertEqual(view.archive[0].details.cite_as, expected)
        block = BeautifulSoup(papers_page(view), "html.parser").select_one(
            ".grove-paper-citation"
        )
        self.assertEqual(tuple(block.stripped_strings), expected)
        self.assertNotIn("[]", block.text)

    def test_older_prepared_details_without_citations_still_render(self):
        view = self.view(publication(1))
        row = view.archive[0]
        evidence = dict(row.provenance["details"]["value"])
        del evidence["cite_as"]
        older = evolve(row, details=PublicationDetails.from_evidence(evidence))
        self.assertEqual(older.details.cite_as, ())
        soup = BeautifulSoup(
            papers_page(evolve(view, publications=(older,))), "html.parser"
        )
        self.assertIsNone(soup.select_one(".grove-paper-citation-panel"))
        self.assertNotIn("Cite as:", soup.text)
        self.assertIn("Synthetic publication", soup.text)
        self.assertIn("Synthetic citation", soup.text)

    def test_custom_single_line_citation_remains_copy_ready_and_escaped(self):
        view = self.view(publication(1))
        row = view.archive[0]
        citation = 'Invented <reference> & "complete citation"'
        custom = evolve(row, details=evolve(row.details, cite_as=(citation,)))
        soup = BeautifulSoup(
            papers_page(evolve(view, publications=(custom,))), "html.parser"
        )
        block = soup.select_one(".grove-paper-citation")
        self.assertEqual(tuple(block.stripped_strings), (citation,))
        self.assertIsNone(block.find("reference"))
        self.assertIsNone(block.find("br"))

    def test_arxiv_identifiers_only_come_from_recognized_paths_and_hosts(self):
        for url, expected in (
            ("https://arxiv.org/abs/9901.12345", "arXiv:9901.12345"),
            ("http://export.arxiv.org/pdf/hep-ex/9901999v2", "arXiv:hep-ex/9901999v2"),
            ("https://arxiv.org/pdf/9901.12345v2.pdf", "arXiv:9901.12345v2"),
            ("https://example.test/abs/9901.12345", None),
            ("https://arxiv.org.example.test/abs/9901.12345", None),
            ("https://arxiv.org/help", None),
            ("https://[invalid", None),
        ):
            with self.subTest(url=url):
                self.assertEqual(arxiv_reference(url), expected or url)

    def test_new_title_fields_round_trip_without_inventing_missing_values(self):
        api = api_fixture()
        paper = api["papers"][0]
        paper["status"] = "Publication Phase Finished"
        paper["publicationPhase"] = {}
        missing = curate(api)["papers"][0]
        self.assertNotIn("fullTitle", missing)
        self.assertNotIn("finalTitleTex", missing["publicationPhase"])
        for title in (None, "", r"Invented $X \to Y$ title"):
            with self.subTest(title=title):
                paper["fullTitle"] = title
                paper["publicationPhase"]["finalTitleTex"] = title
                loaded = CuratedRegistry(curate(api)).records("papers")[0]
                self.assertEqual(loaded["fullTitle"], title)
                self.assertEqual(loaded["publicationPhase"]["finalTitleTex"], title)
        for field in ("fullTitle", "finalTitleTex"):
            invalid = copy.deepcopy(curate(api))
            target = invalid["papers"][0]
            if field == "finalTitleTex":
                target = target["publicationPhase"]
            target[field] = ["not a title string"]
            with self.subTest(field=field), self.assertRaises(ValueError):
                CuratedRegistry(invalid)
