# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Group selections, traceability and rendering using independently invented data."""

import json
import subprocess
import sys
import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from test_curated_registry import api_fixture

from analysis_lister import cli
from analysis_lister.registry import CuratedRegistry
from analysis_lister.registry.enrichment import curate
from analysis_lister.views.build import render_group
from analysis_lister.views.markdown.pages import (
    ongoing_page,
)
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.selection import prepare_group
from analysis_lister.views.semantics import (
    analysis_state,
    last_milestone,
)

ROOT = Path(__file__).resolve().parents[1]


def analysis(number, *, group="DEMO", status="Phase 0 Active", additional=()):
    return {
        "referenceCode": f"ANA-DEMO-2099-{number:02}",
        "status": status,
        "shortTitle": "Invented | title [link] <tag>",
        "gal_analysisContacts": ["Example Contact"],
        "gal_contactEditors": [],
        "gal_groups": {
            "leadingGroup": group,
            "otherGroups": list(additional),
            "leadingSubgroup": "Example subgroup, with comma",
            "subgroups": [],
        },
        "metadata": {"gal_keywords": ["Synthetic"]},
        "phase0": {"startDate": "2099-01-01", "gal_editorialBoard": []},
        "relatedPublications": [],
    }


def publication(
    number,
    *,
    resource="papers",
    group="DEMO",
    related=None,
    status="Publication Phase Finished",
    date="2099-02-01",
):
    key = "referenceCode" if resource == "papers" else "temporaryReferenceCode"
    prefix = {"papers": "", "confnotes": "CONF-", "pubnotes": "PUB-"}[resource]
    value = {
        key: f"{prefix}DEMO-2099-{number:02}",
        "status": status,
        "shortTitle": "Synthetic publication",
        "publicShortTitle": "Synthetic public title",
        "gal_analysisContacts": [],
        "gal_contactEditors": [],
        "gal_groups": {
            "leadingGroup": group,
            "otherGroups": [],
            "leadingSubgroup": None,
            "subgroups": [],
        },
        "relatedAnalysis": {"type": "Analysis", "referenceCode": related}
        if related
        else None,
    }
    if resource == "papers":
        value["publicationPhase"] = {
            "publishedOnlineDate": date,
            "arXivSubmissionDate": None,
            "gal_dois": [
                {"doi": "10.9999/synthetic", "citation": "Synthetic citation"}
            ],
        }
    else:
        value["finalReferenceCode"] = (
            f"{'ATLAS-CONF' if resource == 'confnotes' else 'ATL-PHYS-PUB'}-2099-{number:03}"
        )
        value["phase1"] = {
            "releaseDate": date,
            "publicWebPageUrlForFiguresAndTables": "https://example.test/note",
        }
    return value


def snapshot(*analyses, papers=(), confnotes=(), pubnotes=()):
    data = curate(api_fixture(), {})
    data["analyses"] = list(analyses) or [analysis(99, group="OTHER", status="Closed")]
    for resource, records in (
        ("papers", papers),
        ("confnotes", confnotes),
        ("pubnotes", pubnotes),
    ):
        data[resource] = list(records) or [
            publication(99, resource=resource, group="OTHER", status="Closed")
        ]
    data["counts"] = {
        key: len(data[key]) for key in ("analyses", "papers", "confnotes", "pubnotes")
    }
    return data


class GroupViewTests(unittest.TestCase):
    def prepare(self, data, group="DEMO", **options):
        return prepare_group(CuratedRegistry(data), GroupProfile(group, **options))

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
        self.assertEqual(decision.rule, "analysis-state/v1")
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

    def test_command_writes_ongoing_page_and_hashed_report_without_touching_input(self):
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

            collision = root / "ongoing.md"
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
from analysis_lister.views.profiles import GroupProfile
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
        from analysis_lister.views.semantics import approval_progress

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
        self.assertEqual(decision.rule, "analysis-approval-progress/v2")

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
            trace["associated_paper_statuses"]["rule"], "associated-paper-status/v1"
        )

    def test_missing_or_active_phase_zero_does_not_invent_paper_status(self):
        from analysis_lister.views.semantics import associated_paper_statuses

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
            markup.index("API snapshot:"), markup.index("## Needs review")
        )
        self.assertGreater(markup.index("[view report]"), markup.index("</section>"))
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
        from analysis_lister.views.semantics import subgroup_button_choices

        decision = subgroup_button_choices(
            "DEMO", ["DEMO-Old", "OTHER-Current", "DEMO-Current"]
        )
        self.assertEqual(
            decision.value, (("DEMO-Current", "DEMO-Current"), ("DEMO-Old", "DEMO-Old"))
        )
        self.assertEqual(decision.rule, "group-subgroup-buttons/v2")


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
            "last-paper-milestone/v2",
        )

    def test_missing_dates_do_not_use_paper_status(self):
        from analysis_lister.views.semantics import last_paper_milestone

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
        from analysis_lister.views.semantics import last_paper_milestone

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
            all(t["review_order"]["rule"] == "analysis-review-order/v2" for t in traces)
        )

    def test_later_tick_outweighs_all_earlier_ticks(self):
        from analysis_lister.views.models import Decision
        from analysis_lister.views.semantics import analysis_review_order

        def rank(ticks):
            return analysis_review_order(
                Decision(
                    "test/v1",
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
