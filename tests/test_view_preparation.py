# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Prepared collections, state evidence and relationship provenance."""

import copy
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.analysis_states import analysis_state, last_milestone
from analysis_lister.views.markdown.pages import (
    papers_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.publication_states import publication_state

ROOT = Path(__file__).resolve().parents[1]


class PreparationTests(unittest.TestCase):
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
        self.assertEqual(row.metadata["subgroups"], ["Example subgroup, with comma"])
        self.assertEqual(row.metadata["publication_type"], "papers")
        self.assertEqual(view.controls["within_categories"], "or")
        self.assertEqual(view.controls["between_categories"], "and")
        self.assertEqual(
            "current snapshot" in row.provenance["subgroups"]["reason"], True
        )
        self.assertIn("Synthetic citation", row.metadata["text"])
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

    def test_trigger_and_tool_metadata_inherit_only_through_explicit_links(self):
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
            rows[inherited["referenceCode"]].metadata["triggers"],
            ["Synthetic trigger"],
        )
        self.assertEqual(
            rows[direct["referenceCode"]].metadata["statistical_tools"],
            ["Own tool"],
        )
        self.assertEqual(rows[unlinked["referenceCode"]].metadata["triggers"], [])
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


if __name__ == "__main__":
    unittest.main()
