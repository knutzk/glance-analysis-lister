# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Ongoing cards, subgroup controls, milestones and navigation."""

import json
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import (
    ongoing_page,
    papers_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[1]


class ApprovalProgressTests(unittest.TestCase):
    def test_milestones_require_independent_evidence(self):
        from analysis_lister.views.analysis_states import approval_progress

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
        self.assertNotIn("Internal-note editors", markup.get_text())
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
        from analysis_lister.views.analysis_states import associated_paper_statuses

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
        self.assertEqual(
            view.controls["ongoing"]["subgroups"], (("DEMO-Beta", "DEMO-Beta"),)
        )
        self.assertEqual(
            view.ongoing[0].metadata["subgroups"], ["OTHER-Alpha", "DEMO-Beta"]
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
            labels[labels.index("Analysis contacts") + 1], "Contact editors"
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
        from analysis_lister.views.publication_states import last_paper_milestone

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
        from analysis_lister.views.publication_states import last_paper_milestone

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
        orders = [row.metadata["stage_order"] for row in view.ongoing]
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
        from analysis_lister.views.analysis_states import analysis_review_order
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


if __name__ == "__main__":
    unittest.main()
