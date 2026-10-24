# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Group selections, traceability and rendering using independently invented data."""

import copy
import json
import subprocess
import sys
import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from view_fixtures import analysis, publication, snapshot

from analysis_lister import cli
from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.analyses import analysis_state, last_milestone
from analysis_lister.views.build import render_group
from analysis_lister.views.markdown.links import external
from analysis_lister.views.markdown.pages import (
    confnotes_page,
    ongoing_page,
    papers_page,
    pubnotes_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy
from analysis_lister.views.publications import publication_state

ROOT = Path(__file__).resolve().parents[1]


class GroupViewTests(unittest.TestCase):
    def prepare(self, data, group="DEMO", **options):
        return prepare_group(CuratedRegistry(data), GroupProfile(group, **options))

    def test_distributed_curated_example_has_all_publication_types(self):
        registry = CuratedRegistry.from_json(ROOT / "examples/synthetic_registry.json")
        view = prepare_group(registry, GroupProfile("DEMO"))
        self.assertEqual(len(view.ongoing), 1)
        self.assertEqual(
            {row.resource for row in view.archive}, {"papers", "confnotes", "pubnotes"}
        )
        self.assertEqual(len(view.archive), 3)

    def test_leading_and_additional_membership_not_subgroups_controls_unique_rows(self):
        first = analysis(1, additional=("DEMO",))
        second = analysis(2, group="OTHER", additional=("DEMO",))
        excluded = analysis(3, group="OTHER")
        excluded["gal_groups"]["subgroups"] = ["DEMO"]
        view = self.prepare(snapshot(first, second, excluded))
        self.assertEqual(
            [row.reference for row in view.ongoing],
            [first["referenceCode"], second["referenceCode"]],
        )
        self.assertEqual(
            len(self.prepare(snapshot(first, second, excluded), group="OTHER").ongoing),
            2,
        )
        self.assertEqual(
            view.ongoing[0].groups["leadingSubgroup"], "Example subgroup, with comma"
        )
        with self.assertRaisesRegex(ValueError, "No leading or additional"):
            self.prepare(snapshot(first), group="MISSING")

    def test_states_milestones_and_terminal_precedence_are_traceable(self):
        value = analysis(1)
        self.assertEqual(analysis_state(value, []).value, "phase0")
        value["phase0"]["gal_editorialBoard"] = ["Example Reviewer"]
        self.assertEqual(analysis_state(value, []).value, "editorial_review")
        value["phase0"]["pgcOrSgcSignOffDate"] = "2099-01-03T12:00:00Z"
        decision = analysis_state(value, [])
        self.assertEqual(decision.value, "preapproved")
        self.assertEqual(decision.rule, "analysis-state")
        self.assertIn("phase0.pgcOrSgcSignOffDate", decision.inputs)
        value["phase0"]["gal_approvalMeetingDates"] = ["2099-01-03"]
        self.assertEqual(
            last_milestone(value).value, ("Approval meeting", "2099-01-03")
        )
        self.assertEqual(
            analysis_state(value, [{"state": "submitted"}]).value, "completed"
        )
        for status, state in (
            ("Closed", "closed"),
            ("Created", "not_started"),
            ("Unexpected", "unknown"),
        ):
            value["status"] = status
            self.assertEqual(
                analysis_state(value, [{"state": "under_review"}]).value, state
            )

    def test_relationships_use_native_ids_and_report_contradictions_and_dangling_links(
        self,
    ):
        first = analysis(1, status="Phase 0 Finished")
        second = analysis(2, status="Phase 0 Finished")
        paper = publication(
            1, related=second["referenceCode"], status="Phase 2 Active", date=None
        )
        first["relatedPublications"] = [
            {"type": "Paper", "referenceCode": paper["referenceCode"]},
            {"type": "Paper", "referenceCode": "DEMO-2099-404"},
        ]
        data = snapshot(first, second, papers=(paper,))
        view = self.prepare(data)
        self.assertEqual(
            [row.reference for row in view.ongoing], [second["referenceCode"]]
        )
        self.assertEqual(
            [row.reference for row in view.needs_review], [first["referenceCode"]]
        )
        trace = next(
            trace
            for trace in view.decisions
            if trace["reference"] == first["referenceCode"]
        )
        self.assertEqual(len(trace["relationship_issues"]), 2)
        self.assertIn("different analysis", trace["relationship_issues"][0]["reason"])
        self.assertEqual(view.ongoing[0].stage, "publication_review")

    def test_one_way_links_are_usable_and_explicitly_reported(self):
        value = analysis(1, status="Phase 0 Finished")
        paper = publication(1, status="Phase 1 Active", date=None)
        value["relatedPublications"] = [
            {"type": "Paper", "referenceCode": paper["referenceCode"]}
        ]
        view = self.prepare(snapshot(value, papers=(paper,)))
        self.assertEqual(len(view.ongoing), 1)
        trace = next(
            trace for trace in view.decisions if trace["resource"] == "analyses"
        )
        self.assertEqual(
            trace["relationship_issues"][0]["reason"], "one-way publication link"
        )

    def test_publication_collection_keeps_independent_records_and_filter_provenance(
        self,
    ):
        value = analysis(1)
        inherited = publication(
            1, group=None, related=value["referenceCode"], date="1999-01-01"
        )
        explicit_other = publication(2, group="OTHER", related=value["referenceCode"])
        direct = publication(3)
        direct["gal_groups"]["subgroups"] = ["Direct subgroup"]
        data = snapshot(value, papers=(inherited, explicit_other, direct))
        before = copy.deepcopy(data)
        view = self.prepare(data)
        self.assertEqual(
            {row.reference for row in view.publications},
            {
                inherited["referenceCode"],
                explicit_other["referenceCode"],
                direct["referenceCode"],
            },
        )
        row = next(
            row
            for row in view.publications
            if row.reference == inherited["referenceCode"]
        )
        self.assertEqual(row.subgroups, ("Example subgroup, with comma",))
        self.assertEqual(
            row.filter_metadata["subgroups"], ["Example subgroup, with comma"]
        )
        self.assertEqual(row.filter_metadata["publication_type"], "papers")
        self.assertEqual(view.publication_filters["within_categories"], "or")
        self.assertEqual(view.publication_filters["between_categories"], "and")
        self.assertEqual(
            view.publication_filters["subgroup_assignment"], "current snapshot"
        )
        self.assertIn("Synthetic citation", row.filter_metadata["text"])
        self.assertEqual(
            row.provenance["citation"]["rule"], "publication-citation-text"
        )
        self.assertIn("inherited", row.provenance["subgroups"]["reason"])
        self.assertEqual(
            row.provenance["membership"]["rule"], "publication-group-fallback"
        )
        self.assertEqual(
            next(
                row
                for row in view.publications
                if row.reference == direct["referenceCode"]
            ).subgroups,
            ("Direct subgroup",),
        )
        self.assertEqual(data, before)

    def test_note_release_evidence_and_historical_superseded_notes(self):
        note = publication(
            1, resource="pubnotes", status="Phase 1 Finished", date="1999-01-01"
        )
        note["supersededBy"] = [{"referenceCode": "DEMO-2099-02", "type": "Paper"}]
        note["gal_finalReferenceCode"] = note.pop("finalReferenceCode")
        self.assertEqual(publication_state(note, "pubnotes").value, "released")
        view = self.prepare(snapshot(analysis(1), pubnotes=(note,)))
        self.assertEqual(view.archive[0].date, "1999-01-01")
        note["gal_finalReferenceCode"] = "PUB-DEMO-2099-01 TEMP"
        self.assertNotEqual(publication_state(note, "pubnotes").value, "released")

    def test_counts_tables_escaping_and_local_links_share_the_prepared_collection(self):
        data = snapshot(
            analysis(1),
            analysis(2, group="OTHER", additional=("DEMO",)),
            analysis(3, status="Closed"),
        )
        view = self.prepare(data)
        ongoing = ongoing_page(view)
        self.assertEqual(
            BeautifulSoup(ongoing, "html.parser").select_one("[data-gal-count]").text,
            "2 analyses",
        )
        self.assertNotIn("<tag>", ongoing)
        soup = BeautifulSoup(ongoing, "html.parser")
        cards = soup.select("article[data-gal-item]")
        self.assertEqual(len(cards), 2)
        self.assertIn("Invented | title [link] <tag>", cards[0].get_text())
        self.assertFalse(soup.find_all("script"))
        self.assertTrue(soup.select_one("[data-gal-controls]").has_attr("hidden"))
        self.assertTrue(all(not card.has_attr("hidden") for card in cards))
        metadata = json.loads(cards[0]["data-gal-metadata"])
        self.assertEqual(metadata["subgroups"], ["Example subgroup, with comma"])
        self.assertEqual(
            set(metadata), {"text", "subgroups", "stage_order", "reference"}
        )
        for button in soup.select("[data-gal-value]"):
            self.assertEqual(button["type"], "button")
            self.assertEqual(button["aria-pressed"], "false")
        self.assertEqual(soup.select_one("[data-gal-count]")["aria-live"], "polite")
        self.assertIn("ref_code=ANA-DEMO-2099-01", ongoing)
        self.assertIn('id="analysis-demo-ana-demo-2099-01"', ongoing)
        self.assertNotIn("ANA-DEMO-2099-03", ongoing)
        self.assertEqual(external("Example", "javascript:alert(1)"), "Example")
        self.assertEqual(external("Example", "https://[invalid"), "Example")
        empty = self.prepare(snapshot(analysis(1, status="Closed")))
        self.assertIn("No analyses currently meet", ongoing_page(empty))

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
                self.assertIn(value, row.filter_metadata["text"])
            if resource == "papers":
                self.assertIn("10.9999/synthetic", row.filter_metadata["text"])
                self.assertIn("Synthetic citation", row.filter_metadata["text"])
            else:
                self.assertIn(
                    "https://cds.cern.ch/record/209900000001",
                    row.filter_metadata["text"],
                )
                self.assertIn("Invented Reader", row.filter_metadata["text"])
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

    def test_archive_dropdowns_use_leading_subgroups_and_recorded_keywords(self):
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
            view.archive[0].filter_metadata["leading_subgroup"], "Leading assignment"
        )

    def test_trigger_and_tool_filters_inherit_only_through_explicit_links(self):
        value = analysis(1)
        value["metadata"].update(
            {
                "gal_triggers": ["Synthetic trigger"],
                "gal_statisticalTools": ["Synthetic tool"],
            }
        )
        inherited = publication(1, related=value["referenceCode"])
        direct = publication(2, related=value["referenceCode"])
        direct["metadata"] = {
            "gal_triggers": ["Own trigger"],
            "gal_statisticalTools": ["Own tool"],
        }
        unlinked = publication(3)
        view = self.prepare(snapshot(value, papers=(inherited, direct, unlinked)))
        rows = {row.reference: row for row in view.archive}
        self.assertEqual(
            rows[inherited["referenceCode"]].filter_metadata["triggers"],
            ["Synthetic trigger"],
        )
        self.assertEqual(
            rows[direct["referenceCode"]].filter_metadata["statistical_tools"],
            ["Own tool"],
        )
        self.assertEqual(
            rows[unlinked["referenceCode"]].filter_metadata["triggers"], []
        )
        trace = rows[inherited["referenceCode"]].provenance["filter_metadata"][
            "triggers"
        ]
        self.assertIn("inherited", trace["reason"])
        self.assertEqual(
            trace["inputs"]["relatedAnalysis"]["referenceCode"], value["referenceCode"]
        )
        soup = BeautifulSoup(papers_page(view), "html.parser")
        self.assertNotIn("Leading:", soup.select_one("tbody").get_text())
        for key in ("keywords", "triggers", "statistical_tools"):
            self.assertIsNone(soup.select_one(f'[data-gal-filter="{key}"]'))

    def test_command_writes_two_pages_and_hashed_report_without_touching_input(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path, output = root / "curated.json", root / "pages"
            path.write_text(json.dumps(snapshot(analysis(1))))
            before = path.read_bytes()
            cli.main(
                [
                    "render-group",
                    "--group",
                    "DEMO",
                    "--snapshot",
                    str(path),
                    "--output-dir",
                    str(output),
                ]
            )
            report = json.loads((output / "view-report.json").read_text())
            self.assertEqual(report["snapshot"]["sha256"], sha256(before).hexdigest())
            self.assertEqual(report["counts"]["ongoing_analyses"], 1)
            self.assertEqual(len(report["decisions"]), 1)
            self.assertEqual(
                report["report_scope"]["other_records_omitted"]["papers"], 1
            )
            self.assertEqual(
                {p.name for p in output.iterdir()},
                {
                    "ongoing.md",
                    "papers.md",
                    "confnotes.md",
                    "pubnotes.md",
                    "view-report.json",
                    "assets",
                },
            )
            self.assertEqual(path.read_bytes(), before)
            generated = {
                str(p.relative_to(output)): p.read_bytes()
                for p in output.rglob("*")
                if p.is_file()
            }
            render_group(path, output, GroupProfile("DEMO"))
            self.assertEqual(
                generated,
                {
                    str(p.relative_to(output)): p.read_bytes()
                    for p in output.rglob("*")
                    if p.is_file()
                },
            )

            collision = root / "papers.md"
            collision.write_bytes(before)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                render_group(collision, root, GroupProfile("DEMO"))
            self.assertEqual(collision.read_bytes(), before)
            with self.assertRaises(ValueError):
                GroupProfile("")

    def test_new_views_do_not_import_legacy_or_network_clients(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "curated.json"
            path.write_text(json.dumps(snapshot(analysis(1))))
            code = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".")
               for name in ("analysis_lister.glance", "analysis_lister.markdown",
                            "analysis_lister.downloaders", "stare", "selenium")):
            raise AssertionError("Forbidden dependency: " + fullname)
sys.meta_path.insert(0, Block())
from analysis_lister.views.build import render_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy
render_group(sys.argv[1], sys.argv[2], GroupProfile("DEMO"))
assert "requests" not in sys.modules
"""
            subprocess.run(
                [sys.executable, "-c", code, str(path), str(Path(directory) / "pages")],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()


class ApprovalProgressTests(unittest.TestCase):
    def test_milestones_require_independent_evidence(self):
        from analysis_lister.views.analyses import approval_progress

        record = analysis(1)
        record["phase0"] = {"gal_approvalMeetingDates": ["2099-01-04"]}
        self.assertFalse(
            any(step["reached"] for step in approval_progress(record, []).value)
        )
        record["phase0"].update(
            {
                "gal_editorialBoard": ["Demo Person"],
                "pgcOrSgcSignOffDate": "2099-01-03T12:00:00Z",
            }
        )
        decision = approval_progress(
            record,
            [
                {
                    "reference": "DEMO-2099-2",
                    "state": "under_review",
                    "resource": "papers",
                    "draftReleasedDate": "2099-01-06",
                    "draft2ReleasedDate": "2099-01-07",
                    "pgcApprovalDate": "2099-01-05",
                }
            ],
        )
        self.assertTrue(all(step["reached"] for step in decision.value))
        self.assertEqual(decision.value[1]["date"], "2099-01-03")
        self.assertEqual(decision.value[2]["date"], "2099-01-05")
        self.assertIsNone(decision.value[0]["date"])
        self.assertEqual(decision.rule, "analysis-approval-progress")

    def test_card_exposes_milestones_people_and_trace(self):
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1))), GroupProfile("DEMO")
        )
        markup = BeautifulSoup(ongoing_page(view), "html.parser")
        self.assertEqual(len(markup.select(".gal-progress__step")), 5)
        self.assertIn("Internal-note editors", markup.get_text())
        trace = next(item for item in view.decisions if item["resource"] == "analyses")
        self.assertIn("approval_progress", trace)
        self.assertIn("email_lists", trace)
        self.assertTrue(markup.select('a[href^="mailto:atlas-demo-2099-"]'))


class CirculationCardTests(unittest.TestCase):
    def test_linked_paper_circulations_and_chair_labels(self):
        value = analysis(1)
        value["phase0"]["gal_editorialBoard"] = ["Invented Chair", "Invented Member"]
        value["phase0"]["gal_editorialBoardChairs"] = ["Invented Chair"]
        paper = publication(
            1, related=value["referenceCode"], status="Phase 2 Active", date=None
        )
        paper["phase1"] = {"draftReleasedDate": "2099-02-01T12:00:00Z"}
        paper["phase2"] = {"draft2ReleasedDate": None}
        view = prepare_group(
            CuratedRegistry(snapshot(value, papers=(paper,))), GroupProfile("DEMO")
        )
        self.assertTrue(view.ongoing[0].progress[3]["reached"])
        self.assertFalse(view.ongoing[0].progress[4]["reached"])
        markup = BeautifulSoup(ongoing_page(view), "html.parser")
        card = markup.select_one(".gal-card")
        self.assertIn("Invented Chair (chair)", card.get_text())
        self.assertNotIn("Invented Member (chair)", card.get_text())
        self.assertNotIn("derived from analysis identifier", card.get_text())
        self.assertTrue(
            any(
                paper["referenceCode"] in link.get("href", "")
                for link in card.select("a")
            )
        )
        for email in card.select('a[href^="mailto:"]'):
            self.assertEqual(email.get_text(), email["href"].removeprefix("mailto:"))


class AssociatedPaperStatusTests(unittest.TestCase):
    def test_finished_analysis_shows_linked_native_paper_status(self):
        value = analysis(1, status="Phase 0 Finished")
        paper = publication(
            1, related=value["referenceCode"], status="Phase 2 Active", date=None
        )
        view = prepare_group(
            CuratedRegistry(snapshot(value, papers=(paper,))), GroupProfile("DEMO")
        )
        self.assertEqual(view.ongoing[0].paper_statuses[0]["status"], "Phase 2 Active")
        markup = BeautifulSoup(ongoing_page(view), "html.parser").get_text()
        self.assertNotIn("GLANCE analysis status", markup)
        self.assertNotIn("Paper status", markup)
        trace = next(item for item in view.decisions if item["resource"] == "analyses")
        self.assertEqual(
            trace["associated_paper_statuses"]["rule"], "associated-paper-status"
        )

    def test_missing_or_active_phase_zero_does_not_invent_paper_status(self):
        from analysis_lister.views.analyses import associated_paper_statuses

        self.assertEqual(
            associated_paper_statuses(
                analysis(1), [{"reference": "DEMO-2099-01", "status": "Phase 1 Active"}]
            ).value,
            [],
        )
        self.assertEqual(
            associated_paper_statuses(
                analysis(1, status="Phase 0 Finished"),
                [{"reference": "DEMO-2099-01", "status": None}],
            ).value,
            [],
        )


class PageFooterTests(unittest.TestCase):
    def test_ongoing_metadata_and_review_list_follow_cards(self):
        view = prepare_group(
            CuratedRegistry(
                snapshot(analysis(1), analysis(2, status="Phase 0 Finished"))
            ),
            GroupProfile("DEMO"),
        )
        markup = ongoing_page(view)
        self.assertGreater(markup.index("## Needs review"), markup.index("</section>"))
        self.assertGreater(
            markup.index("GLANCE data extracted:"), markup.index("## Needs review")
        )
        self.assertNotIn("view-report.json", markup)
        self.assertIn("- [ANA-DEMO-2099-02]", markup)
        self.assertNotIn("| Analysis | Title |", markup)


class SubgroupButtonTests(unittest.TestCase):
    def test_namespace_buttons_include_additional_assignments_only_for_own_group(self):
        value = analysis(1)
        value["gal_groups"].update(
            {"leadingSubgroup": "OTHER-Alpha", "subgroups": ["DEMO-Beta"]}
        )
        view = prepare_group(CuratedRegistry(snapshot(value)), GroupProfile("DEMO"))
        self.assertEqual(view.subgroup_buttons, (("DEMO-Beta", "DEMO-Beta"),))
        self.assertEqual(
            view.ongoing[0].filter_metadata["subgroups"], ["OTHER-Alpha", "DEMO-Beta"]
        )
        for page in (ongoing_page(view),):
            soup = BeautifulSoup(page, "html.parser")
            self.assertEqual(
                [
                    b["data-gal-value"]
                    for b in soup.select('[data-gal-filter="subgroups"] button')
                ],
                ["DEMO-Beta"],
            )
            self.assertNotIn("Leading subgroup (snapshot)", page)

    def test_namespace_includes_historical_names_without_configuration(self):
        from analysis_lister.views.common import subgroup_button_choices

        decision = subgroup_button_choices(
            "DEMO", ["DEMO-Old", "OTHER-Current", "DEMO-Current"]
        )
        self.assertEqual(
            decision.value, (("DEMO-Current", "DEMO-Current"), ("DEMO-Old", "DEMO-Old"))
        )
        self.assertEqual(decision.rule, "group-subgroup-buttons")


class PageSubgroupChoicesTests(unittest.TestCase):
    def test_choices_require_matches_in_each_page_collection(self):
        active = analysis(1)
        active["gal_groups"].update(
            {"leadingSubgroup": "DEMO-Active", "subgroups": ["DEMO-Additional"]}
        )
        historical = publication(1)
        historical["gal_groups"].update(
            {"leadingSubgroup": "DEMO-Historical", "subgroups": []}
        )
        view = prepare_group(
            CuratedRegistry(snapshot(active, papers=(historical,))),
            GroupProfile("DEMO"),
        )
        for page, expected in (
            (ongoing_page(view), ["DEMO-Active", "DEMO-Additional"]),
            (papers_page(view), []),
        ):
            soup = BeautifulSoup(page, "html.parser")
            buttons = soup.select('[data-gal-filter="subgroups"] button')
            self.assertEqual([button["data-gal-value"] for button in buttons], expected)
            if expected:
                self.assertLess(
                    page.index('data-gal-filter="subgroups"'),
                    page.index('class="gal-filter-actions"'),
                )


class OngoingTextSearchTests(unittest.TestCase):
    def test_keywords_and_triggers_are_searchable_without_dropdowns(self):
        record = analysis(1)
        record["metadata"].update(
            {"gal_keywords": ["Invented keyword"], "gal_triggers": ["Invented trigger"]}
        )
        view = prepare_group(CuratedRegistry(snapshot(record)), GroupProfile("DEMO"))
        soup = BeautifulSoup(ongoing_page(view), "html.parser")
        self.assertFalse(
            soup.select('[data-gal-filter="keywords"], [data-gal-filter="triggers"]')
        )
        metadata = json.loads(soup.select_one(".gal-card")["data-gal-metadata"])
        self.assertIn("Invented keyword", metadata["text"])
        self.assertIn("Invented trigger", metadata["text"])
        self.assertIsNotNone(
            soup.select_one(".gal-filter-action-buttons [data-gal-expand-all]")
        )
        self.assertIsNotNone(
            soup.select_one(".gal-filter-action-buttons [data-gal-reset]")
        )


class FoldedMilestoneTests(unittest.TestCase):
    def test_latest_paper_date_and_folded_contact_order(self):
        value = analysis(1, status="Phase 0 Finished")
        paper = publication(
            1, related=value["referenceCode"], status="Phase 2 Active", date=None
        )
        paper["phase1"] = {"draftReleasedDate": "2099-02-01T12:00:00Z"}
        paper["phase2"] = {"draft2ReleasedDate": "2099-03-01"}
        view = prepare_group(
            CuratedRegistry(snapshot(value, papers=(paper,))), GroupProfile("DEMO")
        )
        card = BeautifulSoup(ongoing_page(view), "html.parser").select_one(".gal-card")
        folded = card.select_one(".gal-card__details")
        self.assertIn("Phase 2 · ATLAS circulation 2 · 2099-03-01", folded.get_text())
        labels = [label.text for label in folded.select("dt")]
        self.assertEqual(
            labels[labels.index("Analysis contacts") + 1], "Internal-note editors"
        )
        self.assertEqual(labels[0], "Last phase-0 milestone")
        self.assertFalse(
            card.select(".gal-card__fields:not(.gal-card__details .gal-card__fields)")
        )
        self.assertEqual(
            view.ongoing[0].paper_milestones[0]["milestone"]["rule"],
            "last-paper-milestone",
        )

    def test_missing_dates_do_not_use_paper_status(self):
        from analysis_lister.views.publications import last_paper_milestone

        self.assertIsNone(
            last_paper_milestone(
                {
                    "status": "Phase 2 Active",
                    "phase2": {"draft2ReleasedDate": "invalid"},
                }
            ).value
        )


class PaperMilestonePhaseTests(unittest.TestCase):
    def test_milestone_labels_identify_source_phase(self):
        from analysis_lister.views.publications import last_paper_milestone

        for section, field, expected in (
            ("phase1", "draftReleasedDate", "Phase 1 · ATLAS circulation 1"),
            ("phase2", "draft2ReleasedDate", "Phase 2 · ATLAS circulation 2"),
            (
                "publicationPhase",
                "arXivSubmissionDate",
                "Submission · arXiv submission",
            ),
        ):
            with self.subTest(section=section):
                decision = last_paper_milestone({section: {field: "2099-01-02"}})
                self.assertEqual(decision.value, (expected, "2099-01-02"))


class CardNavigationTests(unittest.TestCase):
    def test_card_permalink_and_batch_control_are_rendered(self):
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1))), GroupProfile("DEMO")
        )
        soup = BeautifulSoup(ongoing_page(view), "html.parser")
        card = soup.select_one(".gal-card")
        link = card.select_one(".gal-card__permalink")
        self.assertEqual(link["href"], "#" + card["id"])
        self.assertTrue(link["aria-label"])
        self.assertEqual(soup.select_one("[data-gal-expand-all]").text, "Expand all")
        self.assertFalse(
            BeautifulSoup(papers_page(view), "html.parser").select(
                "[data-gal-expand-all]"
            )
        )


class PaperReviewOrderTests(unittest.TestCase):
    def test_same_paper_status_is_ordered_by_visible_circulation_ticks(self):
        values = [analysis(n, status="Phase 0 Finished") for n in range(1, 4)]
        papers = [
            publication(
                n, related=value["referenceCode"], status="Phase 2 Active", date=None
            )
            for n, value in enumerate(values, 1)
        ]
        papers[0]["phase1"] = {"draftReleasedDate": "2099-03-01"}
        papers[1]["phase1"] = {"draftReleasedDate": "2099-01-01"}
        papers[1]["phase2"] = {"draft2ReleasedDate": "2099-02-01"}
        view = prepare_group(
            CuratedRegistry(snapshot(*values, papers=tuple(papers))),
            GroupProfile("DEMO"),
        )
        orders = [row.filter_metadata["stage_order"] for row in view.ongoing]
        self.assertEqual(orders, [8, 24, 0])
        self.assertGreater(orders[1], orders[0])
        cards = BeautifulSoup(ongoing_page(view), "html.parser").select(".gal-card")
        for card in cards:
            visible_key = sum(
                1 << i
                for i, step in enumerate(card.select(".gal-progress__step"))
                if "gal-progress__step--reached" in step.get("class", [])
            )
            self.assertEqual(
                json.loads(card["data-gal-metadata"])["stage_order"], visible_key
            )
        traces = [t for t in view.decisions if t["resource"] == "analyses"]
        self.assertTrue(
            all(t["review_order"]["rule"] == "analysis-review-order" for t in traces)
        )

    def test_later_tick_outweighs_all_earlier_ticks(self):
        from analysis_lister.views.analyses import analysis_review_order
        from analysis_lister.views.models import Decision

        def rank(ticks):
            return analysis_review_order(
                Decision(
                    "test",
                    [{"reached": tick} for tick in ticks],
                    "synthetic ticks",
                    {},
                )
            ).value

        for index in range(1, 5):
            later = [i == index for i in range(5)]
            earlier = [i < index for i in range(5)]
            self.assertGreater(rank(later), rank(earlier))
        self.assertEqual(rank([False] * 5), 0)


class CardGlanceButtonTests(unittest.TestCase):
    def test_glance_links_are_visible_and_title_has_no_identifier(self):
        value = analysis(1, status="Phase 0 Finished")
        paper = publication(
            1, related=value["referenceCode"], status="Phase 1 Active", date=None
        )
        view = prepare_group(
            CuratedRegistry(snapshot(value, papers=(paper,))), GroupProfile("DEMO")
        )
        page = ongoing_page(view)
        card = BeautifulSoup(page, "html.parser").select_one(".gal-card")
        self.assertEqual(card.select_one("h2").text, value["shortTitle"])
        buttons = card.select(".gal-card__title-line .gal-glance-button")
        self.assertEqual(
            [button.text for button in buttons],
            [value["referenceCode"], paper["referenceCode"]],
        )
        self.assertTrue(
            all(
                button.find_parent(class_="gal-card__details") is None
                for button in buttons
            )
        )
        self.assertFalse(card.select(".gal-card__details a[href*=atlas-glance]"))
        self.assertIn("Click a collapsed card for more information and links", page)


class SeparatePublicationPageTests(unittest.TestCase):
    def test_resources_have_separate_pages_and_only_papers_have_search(self):
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


class ConfNoteTableTests(unittest.TestCase):
    def test_conf_note_row_has_only_requested_columns_and_public_identifier(self):
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["phase1"]["draftCdsUrl"] = "https://cds.cern.ch/record/209900000001"
        note["gal_groups"]["leadingSubgroup"] = "DEMO-Alpha"
        note["gal_groups"]["subgroups"] = ["DEMO-Beta"]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        self.assertEqual(
            [th.text for th in soup.select("thead th")],
            ["Identifier", "Title", "Release date"],
        )
        row = soup.select_one("tbody tr")
        cells = row.select(":scope > td, :scope > th")
        self.assertEqual(len(cells), 3)
        self.assertEqual(
            [link.text for link in cells[0].select("a")],
            [
                note.get("finalReferenceCode") or note.get("gal_finalReferenceCode"),
                "CDS",
            ],
        )
        self.assertIn(note["temporaryReferenceCode"], cells[0].a["href"])
        self.assertEqual(cells[0].select("a")[1]["href"], note["phase1"]["draftCdsUrl"])
        self.assertEqual(cells[0].a.text, note["finalReferenceCode"])
        self.assertNotIn(note["temporaryReferenceCode"], row.get_text())
        self.assertEqual(cells[1].text, note["shortTitle"])
        self.assertEqual(cells[2].text, note["phase1"]["releaseDate"])
        self.assertFalse(
            soup.select(
                "[data-gal-disclosure], details, .gal-publication-details__body, [data-gal-pagination]"
            )
        )
        self.assertFalse(soup.select('[data-gal-filter="subgroups"]'))
        self.assertIsNotNone(soup.select_one("[data-gal-search]"))
        self.assertTrue(soup.select_one("[data-gal-note-controls]").has_attr("hidden"))
        self.assertFalse(row.has_attr("hidden"))
        evidence = next(
            r for r in view.archive if r.resource == "confnotes"
        ).provenance["details"]["inputs"]["cds_record"]
        self.assertEqual(evidence["rule"], "conf-note-cds-record")

    def test_missing_cds_link_is_blank_without_guessing_a_record(self):
        from analysis_lister.views.notes import note_cds_record

        for value in (
            None,
            "",
            "javascript:alert(1)",
            "https://example.test/record/1",
            "https://cds.cern.ch/not-a-record",
        ):
            self.assertIsNone(
                note_cds_record({"phase1": {"draftCdsUrl": value}}, "confnotes").value
            )
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        self.assertEqual(
            [
                a.text
                for a in soup.select_one("[data-gal-note]").select("th:first-child a")
            ],
            [note["finalReferenceCode"]],
        )


class ConfNoteExpansionTests(unittest.TestCase):
    def test_people_and_tags_are_rendered_without_review_dates(self):
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["gal_analysisContacts"] = ["Invented Contact"]
        note["gal_groups"].update(
            {"leadingSubgroup": "DEMO-Alpha", "subgroups": ["DEMO-Beta"]}
        )
        note["phase1"].update(
            {
                "gal_editorialBoard": ["Invented Member"],
                "gal_editorialBoardChairs": ["Invented Chair"],
                "firstSignOffDate": "2099-01-03T10:00:00Z",
            }
        )
        note["metadata"] = {
            "gal_keywords": ["Invented keyword"],
            "gal_statisticalTools": ["Invented tool"],
            "mvaMlTools": [{"name": "Invented ML tool"}],
            "collisions": [{"year": "2099", "ecmValue": "13", "ecmUnit": "TeV"}],
        }
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        detail = soup.select_one("[data-gal-note-details]")
        self.assertEqual(detail.td["colspan"], "3")
        self.assertIn("Invented Chair (chair)", detail.get_text())
        self.assertIn("Invented Contact", detail.get_text())
        self.assertIn("Not recorded", detail.get_text())
        self.assertNotIn("2099-01-03", detail.get_text())
        self.assertEqual(
            [tag.text for tag in detail.select(".gal-note-tags .gal-badge")],
            ["Invented keyword", "Invented tool", "Invented ML tool", "2099 · 13 TeV"],
        )
        self.assertEqual(
            [
                tag.contents[0]
                for tag in detail.select(".gal-card__affiliations .gal-badge--leading")
            ],
            ["DEMO", "DEMO-Alpha"],
        )
        self.assertIn("DEMO-Beta", detail.get_text())
        self.assertTrue(
            detail.select_one("[data-gal-note-collapse]").has_attr("hidden")
        )
        self.assertFalse(detail.has_attr("hidden"))  # Complete static fallback.
        prepared = next(row for row in view.archive if row.resource == "confnotes")
        self.assertEqual(
            prepared.provenance["details"]["inputs"]["conf_note_expansion"]["rule"],
            "conf-note-expansion",
        )


class ConfNoteResponsibleNameTests(unittest.TestCase):
    def test_scalar_responsibles_and_chairs_are_names_not_characters(self):
        from analysis_lister.views.notes import note_expansion

        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["phase1"].update(
            {
                "gal_firstSignOffResponsible": "Invented First Person",
                "gal_secondSignOffResponsible": [
                    "Invented Second Person",
                    "Invented Third Person",
                ],
                "gal_editorialBoard": "Invented Board Member",
                "gal_editorialBoardChairs": "Invented Chair",
            }
        )
        decision = note_expansion(note, "confnotes")
        people = {
            person["label"]: person["names"] for person in decision.value["people"]
        }
        self.assertEqual(
            people["First sign-off responsible"], ["Invented First Person"]
        )
        self.assertEqual(
            people["Second sign-off responsible"],
            ["Invented Second Person", "Invented Third Person"],
        )
        self.assertEqual(
            people["Editorial board"],
            ["Invented Board Member", "Invented Chair (chair)"],
        )
        self.assertEqual(
            decision.inputs["phase1.gal_firstSignOffResponsible"],
            "Invented First Person",
        )
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        markup = (
            BeautifulSoup(confnotes_page(view), "html.parser")
            .select_one("[data-gal-note-details]")
            .get_text()
        )
        self.assertIn("Invented First Person", markup)
        self.assertNotIn("I, n, v, e, n", markup)


class ConfNoteSupersessionTests(unittest.TestCase):
    def test_explicit_links_classify_released_notes_without_target_resolution(self):
        current = publication(1, resource="confnotes", status="Phase 1 Finished")
        superseded = publication(2, resource="confnotes", status="Phase 1 Finished")
        superseded["supersededBy"] = [
            {"type": "Paper", "referenceCode": "DEMO-2099-77"}
        ]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(current, superseded))),
            GroupProfile("DEMO"),
        )
        rows = {
            row.reference: row for row in view.archive if row.resource == "confnotes"
        }
        self.assertFalse(
            rows[current["temporaryReferenceCode"]].details.conf_note.superseded
        )
        self.assertTrue(
            rows[superseded["temporaryReferenceCode"]].details.conf_note.superseded
        )
        self.assertTrue(all(row.state == "released" for row in rows.values()))
        evidence = rows[superseded["temporaryReferenceCode"]].provenance["details"][
            "inputs"
        ]["conf_note_expansion"]["inputs"]["supersession"]
        self.assertEqual(evidence["rule"], "conf-note-supersession")
        self.assertEqual(evidence["inputs"]["supersededBy"], superseded["supersededBy"])
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        self.assertEqual(
            soup.select_one('[data-gal-note-supersession="non-superseded"]')[
                "aria-pressed"
            ],
            "true",
        )
        self.assertEqual(
            soup.select_one('[data-gal-note-supersession="superseded"]')[
                "aria-pressed"
            ],
            "false",
        )
        self.assertEqual(soup.select_one("[data-gal-note-count]").text, "2 of 2 notes")
        self.assertEqual(
            len(soup.select('[data-gal-note][data-gal-superseded="true"]')), 1
        )
        self.assertFalse(
            any(row.has_attr("hidden") for row in soup.select("[data-gal-note]"))
        )


class ConfNoteSupersedingLinksTests(unittest.TestCase):
    def test_superseding_links_use_explicit_native_targets_even_if_absent(self):
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["supersededBy"] = [
            {"type": "Paper", "referenceCode": "DEMO-2099-77"},
            {"type": "CONF note", "referenceCode": "CONF-DEMO-2099-88"},
            {"type": "Analysis", "referenceCode": "ANA-DEMO-2099-99"},
        ]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        links = soup.select(".gal-note-superseders a")
        self.assertEqual(len(links), 3)
        for link, target, resource in zip(
            links,
            note["supersededBy"],
            ["papers", "confnotes", "analyses"],
            strict=True,
        ):
            self.assertIn("/" + resource + "/details.php?", link["href"])
            self.assertIn(target["referenceCode"], link["href"])
            self.assertIn(target["referenceCode"], link.text)
        current = publication(2, resource="confnotes", status="Phase 1 Finished")
        current_view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(current,))),
            GroupProfile("DEMO"),
        )
        self.assertFalse(
            BeautifulSoup(confnotes_page(current_view), "html.parser").select(
                ".gal-note-superseders"
            )
        )


class PubNotePageTests(unittest.TestCase):
    def test_pub_notes_share_note_controls_and_use_public_identifiers_and_readers(self):
        note = publication(1, resource="pubnotes", status="Phase 1 Finished")
        note["gal_finalReferenceCode"] = note.pop("finalReferenceCode")
        note["gal_groups"]["leadingSubgroup"] = "DEMO-Alpha"
        note["phase1"].update(
            {
                "draftCdsUrl": "https://cds.cern.ch/record/209900000001",
                "gal_readers": ["Invented Reader"],
                "gal_firstReaders": "Invented First Reader",
                "gal_secondReaders": [],
            }
        )
        note["supersededBy"] = [{"type": "Paper", "referenceCode": "DEMO-2099-77"}]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), pubnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(pubnotes_page(view), "html.parser")
        summary = soup.select_one("[data-gal-note]")
        cells = summary.select(":scope > td, :scope > th")
        self.assertEqual(len(cells), 3)
        self.assertEqual(cells[0].a.text, "ATL-PHYS-PUB-2099-001")
        self.assertNotIn(note["temporaryReferenceCode"], summary.get_text())
        self.assertIn("/pubnotes/details.php?", cells[0].a["href"])
        self.assertEqual(
            [link.text for link in cells[0].select("a")],
            [
                note.get("finalReferenceCode") or note.get("gal_finalReferenceCode"),
                "CDS",
            ],
        )
        details = soup.select_one("[data-gal-note-details]")
        self.assertIn("Invented Reader", details.get_text())
        self.assertIn("Invented First Reader", details.get_text())
        self.assertIn("Second readers", details.get_text())
        self.assertIn("Not recorded", details.get_text())
        self.assertNotIn("Editorial board", details.get_text())
        self.assertTrue(details.select(".gal-note-superseders a"))
        self.assertTrue(details.select("[data-gal-note-collapse]"))
        self.assertTrue(soup.select("[data-gal-note-supersession]"))
        self.assertEqual(soup.select_one("[data-gal-note-count]").text, "1 of 1 notes")
        row = next(row for row in view.archive if row.resource == "pubnotes")
        self.assertEqual(
            row.provenance["details"]["inputs"]["pub_note_expansion"]["rule"],
            "pub-note-expansion",
        )
        self.assertEqual(
            row.provenance["details"]["inputs"]["cds_record"]["rule"],
            "pub-note-cds-record",
        )


class ArchiveCurationPolicyTests(unittest.TestCase):
    def test_all_resources_use_identifier_or_configured_keywords(self):
        for resource in ("papers", "confnotes", "pubnotes"):
            records = [
                publication(
                    n,
                    resource=resource,
                    group="OTHER",
                    status="Publication Phase Finished"
                    if resource == "papers"
                    else "Phase 1 Finished",
                )
                for n in range(1, 5)
            ]
            key = "referenceCode" if resource == "papers" else "temporaryReferenceCode"
            for n, record in enumerate(records):
                record[key] = f"OTHER-2099-{n:02}"
            records[0][key] = "DEMO-2099-01"
            records[1]["metadata"] = {"gal_keywords": ["INVENTED TOPIC"]}
            records[2]["metadata"] = {"gal_keywords": ["Invented topic suffix"]}
            data = snapshot(analysis(1), **{resource: tuple(records)})
            profile = GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("DEMO",), keywords=("Invented topic",)
                ),
            )
            view = prepare_group(CuratedRegistry(data), profile)
            self.assertEqual(
                {r.reference for r in view.archive}, {records[0][key], records[1][key]}
            )
            self.assertEqual(
                len(prepare_group(CuratedRegistry(data), GroupProfile("DEMO")).archive),
                1,
            )
            with TemporaryDirectory() as folder:
                source = Path(folder) / "input.json"
                source.write_text(json.dumps(data))
                render_group(source, Path(folder) / "out", profile)
                report = json.loads((Path(folder) / "out/view-report.json").read_text())
                self.assertEqual(
                    report["archive_keyword_policy"]["keywords"], ["Invented topic"]
                )
                self.assertFalse((Path(folder) / "out/keyword-survey.md").exists())

    def test_configured_groups_and_subgroups_select_every_publication_type(self):
        for resource in ("papers", "confnotes", "pubnotes"):
            key = "referenceCode" if resource == "papers" else "temporaryReferenceCode"
            records = [
                publication(
                    n,
                    resource=resource,
                    group="OTHER",
                    status="Publication Phase Finished"
                    if resource == "papers"
                    else "Phase 1 Finished",
                )
                for n in range(1, 8)
            ]
            for n, record in enumerate(records):
                record[key] = f"OTHER-2099-{n:02}"
                record["gal_groups"]["leadingSubgroup"] = None
            records[0][key] = "LEGACY-2099-01"
            records[1]["gal_groups"]["leadingGroup"] = "LEGACY"
            records[2]["gal_groups"]["otherGroups"] = ["LEGACY"]
            records[3]["gal_groups"]["leadingSubgroup"] = "OTHER-Merged"
            records[4]["gal_groups"]["subgroups"] = ["OTHER-Merged"]
            records[5]["gal_groups"]["subgroups"] = ["OTHER-Merged-suffix"]
            records[6]["gal_groups"]["leadingGroup"] = "LEGACYX"
            profile = GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("LEGACY",), subgroups=("OTHER-Merged",)
                ),
            )
            view = prepare_group(
                CuratedRegistry(snapshot(analysis(1), **{resource: tuple(records)})),
                profile,
            )
            self.assertEqual(
                {row.reference for row in view.archive},
                {record[key] for record in records[:5]},
            )
            self.assertEqual(len(view.archive), 5)
            trace = next(
                row.provenance["curation"]
                for row in view.archive
                if row.reference == records[4][key]
            )
            self.assertEqual(trace["inputs"]["matching_subgroups"], ["OTHER-Merged"])
            for page in (papers_page(view), confnotes_page(view), pubnotes_page(view)):
                self.assertIn("<dt>Groups</dt><dd><code>LEGACY</code>", page)
                self.assertIn("<dt>Subgroups</dt><dd><code>OTHER-Merged</code>", page)

    def test_configured_affiliations_trace_explicit_analysis_fallback(self):
        own = analysis(1, group="LEGACY")
        own["gal_groups"]["leadingSubgroup"] = "OTHER-Merged"
        paper = publication(1, group=None, related=own["referenceCode"])
        paper["referenceCode"] = "OTHER-2099-01"
        paper["gal_groups"]["leadingSubgroup"] = None
        view = prepare_group(
            CuratedRegistry(snapshot(own, papers=(paper,))),
            GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("LEGACY",), subgroups=("OTHER-Merged",)
                ),
            ),
        )
        self.assertEqual(len(view.archive), 1)
        evidence = view.archive[0].provenance["curation"]["inputs"]
        self.assertEqual(evidence["matching_groups"], ["LEGACY"])
        self.assertEqual(evidence["matching_subgroups"], ["OTHER-Merged"])
        self.assertIn(
            "relatedAnalysis.gal_groups", evidence["affiliation_evidence"]["inputs"]
        )
        self.assertEqual(len(view.ongoing), 0)

    def test_explicit_policy_has_no_implicit_group_and_title_is_publication_only(self):
        import io
        from contextlib import redirect_stdout

        own, foreign = publication(1), publication(2, group="LEGACY")
        foreign["referenceCode"] = "LEGACY-2099-02"
        data = snapshot(analysis(1), papers=(own, foreign))
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "input.json"
            path.write_text(json.dumps(data))
            profile = GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("LEGACY",), title="Invented publication title"
                ),
            )
            view = prepare_group(CuratedRegistry(data), profile)
            self.assertEqual(
                [row.reference for row in view.archive], [foreign["referenceCode"]]
            )
            self.assertEqual(
                len(
                    prepare_group(
                        CuratedRegistry(data),
                        GroupProfile(
                            "DEMO", publication_policy=PublicationPolicy(groups=())
                        ),
                    ).archive
                ),
                0,
            )
            for render in (
                papers_page,
                confnotes_page,
                pubnotes_page,
            ):
                self.assertIn("# Invented publication title", render(view))
            self.assertNotIn("Invented publication title", ongoing_page(view))
            for configured, warn in ((profile, False), (GroupProfile("DEMO"), True)):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    render_group(path, root / "out", configured)
                self.assertEqual("WARNING:" in stdout.getvalue(), warn)

    def test_config_is_optional_and_validated(self):
        from analysis_lister.views.curation import load_publication_policy

        self.assertEqual(load_publication_policy(None, "DEMO"), None)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "curation.toml"
            path.write_text('[groups.DEMO]\nkeywords = ["Invented topic"]\n')
            self.assertEqual(
                load_publication_policy(path, "DEMO"),
                PublicationPolicy(
                    title="", groups=(), subgroups=(), keywords=("Invented topic",)
                ),
            )
            self.assertEqual(load_publication_policy(path, "OTHER"), None)
            path.write_text(
                '[groups.DEMO]\ngroups = ["LEGACY"]\nsubgroups = ["OTHER-Merged"]\n'
            )
            self.assertEqual(
                load_publication_policy(path, "DEMO"),
                PublicationPolicy(
                    groups=("LEGACY",),
                    subgroups=("OTHER-Merged",),
                    title="",
                    keywords=(),
                ),
            )
            path.write_text('[groups.DEMO]\nkeywords = "invalid"\n')
            with self.assertRaises(ValueError):
                load_publication_policy(path, "DEMO")

    def test_cli_loads_keyword_configuration_into_report(self):
        paper = publication(1)
        paper["referenceCode"] = "OTHER-2099-01"
        paper["metadata"] = {"gal_keywords": ["Invented topic"]}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, config, output = (
                root / "input.json",
                root / "curation.toml",
                root / "out",
            )
            source.write_text(json.dumps(snapshot(analysis(1), papers=(paper,))))
            config.write_text(
                '[groups.DEMO]\ntitle = "Invented archive"\ngroups = []\nkeywords = ["Invented topic"]\n'
            )
            cli.main(
                [
                    "render-group",
                    "--group",
                    "DEMO",
                    "--snapshot",
                    str(source),
                    "--output-dir",
                    str(output),
                    "--curation-config",
                    str(config),
                ]
            )
            report = json.loads((output / "view-report.json").read_text())
            self.assertEqual(report["counts"]["archive_publications"], 1)
            self.assertEqual(
                report["profile"]["publication_policy"]["keywords"], ["Invented topic"]
            )
            self.assertIn(
                "<code>Invented topic</code>", (output / "papers.md").read_text()
            )
            self.assertIn(
                "# Invented archive papers", (output / "papers.md").read_text()
            )

    def test_keywords_do_not_select_ongoing_analyses(self):
        own, foreign = analysis(1), analysis(2, group="OTHER")
        foreign["referenceCode"] = "ANA-DEMO-2099-02"
        foreign["metadata"]["gal_keywords"] = ["Invented topic"]
        view = prepare_group(
            CuratedRegistry(snapshot(own, foreign)),
            GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("DEMO",), keywords=("Invented topic",)
                ),
            ),
        )
        self.assertEqual(
            [row.reference for row in view.ongoing], [own["referenceCode"]]
        )
