# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publication rules using synthetic records with GLANCE's exact status strings.

These tests exercise model construction and registry selection together. They do
not depend on live GLANCE data or the maintained snapshot's current contents.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from attrs import asdict, define, field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.confnote import ConfNote
from analysis_lister.glance.enums import PublicationState as State, SoftwareRelease
from analysis_lister.glance.field_maps import (
    REQUIRED_COLUMNS_ANALYSIS,
    REQUIRED_COLUMNS_CONFNOTE,
    REQUIRED_COLUMNS_PAPER,
    REQUIRED_COLUMNS_PUBNOTE,
)
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.glance.paper import Paper
from analysis_lister.glance.pubnote import PubNote

ACTIVE = " Phase 0 is  Active "
FINISHED = " Phase 0 is  Finished "
CLOSED = " Analysis is  Closed "
DOI = "10.1007/JHEP07(2023)203"
COLUMNS = {
    Paper: REQUIRED_COLUMNS_PAPER,
    ConfNote: REQUIRED_COLUMNS_CONFNOTE,
    PubNote: REQUIRED_COLUMNS_PUBNOTE,
}


def analysis(ref="TOPQ-2099-01", status=ACTIVE, **changes):
    row = dict.fromkeys(REQUIRED_COLUMNS_ANALYSIS, "")
    row.update(
        {
            "Reference Code": f"ANA-{ref}",
            "Status": status,
            "Analysis Contacts": "Current Contact, Former Contact",
            "Analysis Contacts' End Date": "No end date, 2020-01-01",
            "Editorial Board": "Editor One, Editor Two",
            "Chairs": "Editor One",
            "Keywords": "R22, test",
            "Subgroups": "TOPQ - Cross-section,TOPQ - Top Properties and Mass",
            "Supporting Documents": "https://example.test/note",
            "Full Title": "Full synthetic title",
            "Short Title": "Synthetic title",
            "Public Short Title": "Public synthetic title",
            "Phase 0 Start Date": "2019-01-01",
        }
    )
    row.update(changes)
    return Analysis.from_csv_dict(row)


def publication_row(cls, ref="TOPQ-2099-01", **changes):
    row = dict.fromkeys(COLUMNS[cls], "")
    if cls is Paper:
        row.update(
            {
                "Reference Code": ref,
                "Short Title": "Synthetic title",
                "Status": " Publication Phase is  Active ",
                "arXiv Submission Date": "2023-01-01",
                "Publication Date": "2023-07-01",
                "ArXiv Reference Number": "arXiv:2301.00001",
                "ArXiv Reference URLs": "https://arxiv.org/abs/2301.00001",
                "Final Journal Publication URLs": f"https://doi.org/{DOI}",
                "Final Title (Tex)": "Final synthetic title",
                "Journal of Final Submission": "JHEP",
            }
        )
    else:
        prefix = "CONF" if cls is ConfNote else "PUB"
        row.update(
            {
                "Temporary Reference Code": f"{prefix}-{ref}",
                "Short Title": "Synthetic title",
                "Reference Code": "ATLAS-CONF-2023-001"
                if cls is ConfNote
                else "ATL-PHYS-PUB-2023-001",
                "Final URL": f"https://example.test/{prefix}/publication",
            }
        )
        if cls is PubNote:
            row["Status"] = " Phase 1 is  Active "
            row["Short Title"] = "Synthetic title"
    row.update(changes)
    return row


def publication(cls, ref="TOPQ-2099-01", *, base_status=FINISHED, **changes):
    return cls.from_analysis_and_dict(
        analysis(ref, base_status), publication_row(cls, ref, **changes)
    )


def registry(*entries, threshold="2020"):
    return GlanceRegistry(
        {entry.ref_code: entry for entry in entries},
        threshold_year=threshold,
        last_modified_time="synthetic sync time",
    )


def refs(entries):
    return {entry.ref_code for entry in entries}


class IndependentPubLoadingTests(unittest.TestCase):
    def test_registry_roundtrip_uses_pub_status_without_analysis_warnings(self):
        for status, final_url, final_ref, expected in (
            (
                " Phase 1 is  Active ",
                "https://example.test/pub",
                "ATL-PHYS-PUB-2099-001",
                State.PUBLISHED,
            ),
            (" Phase 1 is  Active ", "", "PUB-DEMO-2099-01 TEMP", State.PHASE1_OR_2),
            (" Phase 1 is  Not started ", "", "PUB-DEMO-2099-01 TEMP", State.INACTIVE),
            (
                " Publication is  Closed ",
                "https://example.test/pub",
                "ATL-PHYS-PUB-2099-001",
                State.CLOSED,
            ),
        ):
            with (
                self.subTest(status=status, expected=expected),
                TemporaryDirectory() as directory,
            ):
                payload = asdict(publication(PubNote, "DEMO-2099-01"))
                payload.update(
                    ref_code="PUB-DEMO-2099-01",
                    status=status,
                    status_pub=status,
                    final_url=final_url,
                    final_ref_code=final_ref,
                    pub_state="UNKNOWN",
                )
                with self.assertNoLogs(level="WARNING"):
                    note = PubNote.from_json(payload)
                    collection = registry(note)
                    path = Path(directory) / "registry.json"
                    collection.store_json(path)
                    restored = GlanceRegistry.from_json(path)
                loaded = restored.get(note.ref_code)
                self.assertEqual(loaded.pub_state, expected)
                self.assertEqual(loaded.glance_url_analysis, "")
                self.assertTrue(
                    loaded.glance_url_publ.endswith("ref_code=PUB-DEMO-2099-01")
                )
                self.assertNotIn("PUB-PUB-", loaded.glance_url_publ)
                self.assertFalse(loaded.is_ongoing())
                self.assertEqual(restored.analyses, [])
                self.assertEqual(
                    restored.pubnotes, [loaded] if expected == State.PUBLISHED else []
                )


class RenderScopeTests(unittest.TestCase):
    def test_top_pages_filter_every_publication_type_and_keep_cross_group_entries(self):
        from analysis_lister.markdown.mkdown_renderer import MarkdownPageRenderer

        included = analysis("DEMO-2099-01", **{"Subgroups": "TOPQ - Cross-section"})
        outside = analysis("DEMO-2099-02", **{"Subgroups": "OTHER - Synthetic"})
        other_paper = publication(Paper, "DEMO-2099-03")
        other_conf = publication(ConfNote, "DEMO-2099-04")
        other_pub = publication(PubNote, "DEMO-2099-05")
        for entry in (other_paper, other_conf, other_pub):
            entry.subgroups = ["OTHER - Synthetic"]
        collection = registry(included, outside, other_paper, other_conf, other_pub)
        with TemporaryDirectory() as directory, self.assertNoLogs(level="WARNING"):
            output = Path(directory)
            renderer = MarkdownPageRenderer(collection, output, "2020")
            renderer.write_all()
            pages = "\n".join(path.read_text() for path in output.rglob("*.md"))
            self.assertIn(included.ref_code, pages)
            for entry in (outside, other_paper, other_conf, other_pub):
                self.assertNotIn(entry.ref_code, pages)
            self.assertIn(
                "**All ongoing analyses**: 1", (output / "ongoing.md").read_text()
            )
            self.assertEqual(set(renderer.registry.entries), {included.ref_code})
        self.assertEqual(len(collection.entries), 5)

    def test_render_reviews_relationships_against_full_snapshot(self):
        from analysis_lister.lookup_dicts.clones import Clones
        from analysis_lister.render import render_pages

        top = analysis("DEMO-2099-01", **{"Subgroups": "TOPQ - Cross-section"})
        other = analysis("DEMO-2099-02", **{"Subgroups": "OTHER - Synthetic"})
        with (
            patch.dict(Clones, {other.ref_code: top.ref_code}, clear=True),
            TemporaryDirectory() as directory,
        ):
            path = Path(directory) / "registry.json"
            registry(top, other).store_json(path)
            with self.assertLogs(level="INFO") as logs:
                render_pages(path, Path(directory) / "pages")
            self.assertFalse(any("absent from" in line for line in logs.output))
        with (
            patch.dict(Clones, {"DEMO-2099-99": top.ref_code}, clear=True),
            TemporaryDirectory() as directory,
        ):
            path = Path(directory) / "registry.json"
            registry(top).store_json(path)
            with self.assertLogs(level="INFO") as logs:
                render_pages(path, Path(directory) / "pages")
            self.assertTrue(
                any(
                    "DEMO-2099-99" in line and "absent from" in line
                    for line in logs.output
                )
            )

    def test_registry_selection_preserves_clone_exclusions_and_metadata(self):
        from analysis_lister.lookup_dicts.clones import Clones

        note = publication(ConfNote, "DEMO-2099-01")
        paper = publication(Paper, "DEMO-2099-02")
        with patch.dict(Clones, {paper.ref_code: note.ref_code}, clear=True):
            collection = registry(note, paper)
            selected = collection.select(lambda entry: entry is note)
        self.assertTrue(selected.is_clone_excluded(note.ref_code))
        self.assertEqual(selected.confnotes, [])
        self.assertEqual(selected.last_modified_time, collection.last_modified_time)
        self.assertEqual(selected.threshold_year, collection.threshold_year)
        self.assertEqual(len(collection.entries), 2)


class BaselineDiagnosticTests(unittest.TestCase):
    def test_baseline_suppression_restores_model_diagnostics_after_failure(self):
        from analysis_lister.diagnostics import discard_baseline_notices

        with (
            self.assertNoLogs(level="WARNING"),
            self.assertRaisesRegex(ValueError, "synthetic failure"),
            discard_baseline_notices(),
        ):
            publication(Paper, base_status=CLOSED)
            raise ValueError("synthetic failure")
        with self.assertLogs(level="WARNING"):
            publication(Paper, base_status=CLOSED)


class IgnoredAnalysisTests(unittest.TestCase):
    def test_ignored_entries_stay_in_snapshot_but_not_views_or_counts(self):
        from analysis_lister.lookup_dicts.ignored_analyses import IgnoredAnalyses

        entries = [
            analysis("DEMO-2099-01", FINISHED),
            analysis("DEMO-2099-02"),
            publication(Paper, "DEMO-2099-03"),
            publication(ConfNote, "DEMO-2099-04"),
            publication(PubNote, "DEMO-2099-05"),
        ]
        with patch.dict(
            IgnoredAnalyses,
            {entry.ref_code: "Synthetic reviewed exception" for entry in entries},
            clear=True,
        ):
            collection = registry(*entries)
            self.assertEqual(len(collection.entries), 5)
            self.assertEqual(collection.count(lambda entry: True), 0)
            self.assertEqual(
                sum(collection.count_by_state(lambda entry: True).values()), 0
            )
            for view in ("analyses", "papers", "confnotes", "pubnotes", "unaccounted"):
                self.assertEqual(getattr(collection, view), [])
            with self.assertNoLogs(level="WARNING"):
                collection.log_unaccounted()
            with TemporaryDirectory() as directory:
                path = Path(directory) / "registry.json"
                collection.store_json(path)
                restored = GlanceRegistry.from_json(path)
                self.assertEqual(len(restored.entries), 5)
                self.assertEqual(restored.unaccounted, [])
        self.assertEqual(len(collection.unaccounted), 1)
        self.assertEqual(len(collection.papers), 1)


class PublicationSelectionTests(unittest.TestCase):
    def test_analysis_and_publication_closed_together_are_quiet_and_excluded(self):
        for dates in (
            {"arXiv Submission Date": "", "Publication Date": ""},
            {"arXiv Submission Date": "2099-01-01", "Publication Date": "2099-02-01"},
        ):
            with self.subTest(dates=dates), self.assertNoLogs(level="WARNING"):
                entry = publication(
                    Paper,
                    base_status=CLOSED,
                    **({"Status": " Publication is  Closed "} | dates),
                )
                self.assertEqual(entry.pub_state, State.CLOSED)
                restored = Paper.from_json(asdict(entry) | {"pub_state": "UNKNOWN"})
                self.assertEqual(restored.pub_state, State.CLOSED)
            collection = registry(entry)
            for view in ("analyses", "papers", "confnotes", "pubnotes", "unaccounted"):
                self.assertEqual(getattr(collection, view), [], view)

    def test_stale_phase_zero_metadata_is_debug_only_for_attached_papers(self):
        for milestones in (
            {},
            {"Editorial Board Formed On": "2099-01-01"},
            {"PGC or SGC sign-off date": "2099-01-02"},
        ):
            with self.subTest(milestones=milestones):
                base = analysis(status=ACTIVE, **milestones)
                with (
                    self.assertNoLogs(level="WARNING"),
                    self.assertLogs(
                        "analysis_lister.glance.paper", level="DEBUG"
                    ) as logs,
                ):
                    entry = Paper.from_analysis_and_dict(base, publication_row(Paper))
                notice = [
                    record for record in logs.records if "has state" in record.msg
                ]
                self.assertEqual(len(notice), 1)
                self.assertEqual(notice[0].levelname, "DEBUG")
                self.assertEqual(entry.pub_state, State.PUBLISHED)
                self.assertEqual(entry.status, ACTIVE)
                with self.assertNoLogs(level="WARNING"):
                    restored = Paper.from_json(asdict(entry))
                self.assertEqual(restored.pub_state, State.PUBLISHED)

    def test_unknown_analysis_state_still_reports_diagnostics_with_a_paper(self):
        with self.assertLogs(level="WARNING") as logs:
            entry = publication(Paper, base_status=" Unrecognised synthetic state ")
        self.assertTrue(any("Unknown analysis state" in line for line in logs.output))
        self.assertTrue(any("while it should be" in line for line in logs.output))
        self.assertEqual(entry.pub_state, State.PUBLISHED)

    def test_closed_analysis_with_active_publication_still_warns(self):
        with self.assertLogs(level="WARNING") as logs:
            entry = publication(Paper, base_status=CLOSED)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("while it should be", logs.output[0])
        self.assertEqual(entry.pub_state, State.PUBLISHED)

    def test_not_started_is_distinct_and_excluded_even_with_dates_or_publication_data(
        self,
    ):
        status = " Phase 0 is  Not started "
        with self.assertNoLogs(level="WARNING"):
            entries = [
                analysis(
                    status=status,
                    **{
                        "Editorial Board Formed On": "2099-01-01",
                        "PGC or SGC sign-off date": "2099-02-01",
                    },
                ),
                *(
                    publication(cls, f"TOPQ-2099-{index:02}", base_status=status)
                    for index, cls in enumerate((Paper, ConfNote, PubNote), start=2)
                ),
            ]
        collection = registry(*entries)
        for entry in entries:
            self.assertEqual(entry.status, status)
            self.assertEqual(entry.pub_state, State.NOT_STARTED)
            self.assertFalse(entry.is_ongoing())
            payload = asdict(entry) | {"pub_state": "UNKNOWN"}
            self.assertEqual(
                type(entry).from_json(payload).pub_state, State.NOT_STARTED
            )
        self.assertEqual(len(collection.entries), 4)
        for view in ("analyses", "papers", "confnotes", "pubnotes", "unaccounted"):
            self.assertEqual(getattr(collection, view), [], view)

    def test_analysis_milestones_and_terminal_states_control_inclusion(self):
        milestones = {
            "Editorial Board Formed On": "2020-01-01",
            "PGC or SGC sign-off date": "2020-02-01",
        }
        cases = (
            (ACTIVE, {}, State.ONGOING_WO_EB, True),
            (
                ACTIVE,
                {"Editorial Board Formed On": "2020-01-01"},
                State.ONGOING_WITH_EB,
                True,
            ),
            (ACTIVE, milestones, State.PREAPPROVED, True),
            (FINISHED, milestones, State.PAST_PHASE0, False),
            (CLOSED, milestones, State.CLOSED, False),
        )
        for status, changes, expected, ongoing in cases:
            with self.subTest(expected=expected):
                entry = analysis(status=status, **changes)
                collection = registry(entry)
                self.assertEqual(entry.status, status)
                self.assertEqual(entry.pub_state, expected)
                self.assertEqual(
                    refs(collection.analyses), {entry.ref_code} if ongoing else set()
                )
                self.assertEqual(
                    refs(collection.unaccounted),
                    {entry.ref_code} if expected is State.PAST_PHASE0 else set(),
                )

    def test_review_papers_remain_ongoing_until_submission(self):
        for status in (
            " Phase 1 is  Not started ",
            " Phase 1 is  Active ",
            " Phase 2 is  Active ",
            " Publication Phase is  Active ",
        ):
            with self.subTest(status=status):
                with self.assertNoLogs(level="WARNING"):
                    entry = publication(
                        Paper,
                        **{
                            "Status": status,
                            "arXiv Submission Date": "",
                            "Publication Date": "",
                        },
                    )
                collection = registry(entry)
                self.assertEqual(entry.status_paper, status)
                self.assertEqual(entry.pub_state, State.PHASE1_OR_2)
                self.assertEqual(collection.analyses, [entry])
                self.assertEqual(collection.papers, [])

    def test_published_threshold_is_inclusive_and_does_not_filter_submitted_papers(
        self,
    ):
        before = publication(
            Paper,
            "TOPQ-2099-01",
            **{"Publication Date": "2019-12-31", "arXiv Submission Date": "2019-01-01"},
        )
        boundary = publication(
            Paper,
            "TOPQ-2099-02",
            **{"Publication Date": "2020-01-01", "arXiv Submission Date": "2019-01-01"},
        )
        later = publication(
            Paper,
            "TOPQ-2099-03",
            **{"Publication Date": "2020-01-02", "arXiv Submission Date": "2019-01-01"},
        )
        submitted = publication(
            Paper,
            "TOPQ-2099-04",
            **{
                "Publication Date": "",
                "arXiv Submission Date": "2018-01-01",
                "Journal Acceptance Date": "2019-01-01",
            },
        )
        collection = registry(before, boundary, later, submitted)
        self.assertEqual(
            refs(collection.papers),
            {boundary.ref_code, later.ref_code, submitted.ref_code},
        )
        self.assertEqual(submitted.pub_state, State.SUBMITTED_TO_JOURNAL)
        self.assertEqual(submitted.journal_ref, "Submitted to JHEP")
        self.assertEqual(collection.analyses, [])
        self.assertEqual(collection.unaccounted, [])
        collection.threshold_year = "2021"
        self.assertEqual(collection.papers, [submitted])

    def test_note_publication_supersession_closure_and_review(self):
        for cls in (ConfNote, PubNote):
            with self.subTest(cls=cls):
                published = publication(cls, "TOPQ-2099-01")
                superseded = publication(
                    cls, "TOPQ-2099-02", **{"Superseded By": "TOPQ-2099-01"}
                )
                closed = publication(cls, "TOPQ-2099-03", base_status=CLOSED)
                prefix = "CONF" if cls is ConfNote else "PUB"
                review = publication(
                    cls,
                    "TOPQ-2099-04",
                    **{
                        "Reference Code": f"{prefix}-TOPQ-2099-04  TEMP ",
                        "Final URL": "",
                    },
                )
                collection = registry(published, superseded, closed, review)
                listed = (
                    collection.confnotes if cls is ConfNote else collection.pubnotes
                )
                self.assertEqual(listed, [published])
                self.assertEqual(superseded.pub_state, State.SUPERSEDED)
                self.assertEqual(closed.pub_state, State.CLOSED)
                self.assertEqual(review.pub_state, State.PHASE1_OR_2)
                self.assertEqual(collection.analyses, [review])
                self.assertEqual(collection.unaccounted, [])

    def test_inactive_pubnote_is_not_listed_even_with_final_url(self):
        entry = publication(PubNote, **{"Status": " Phase 1 is  Not started "})
        collection = registry(entry)
        self.assertEqual(entry.pub_state, State.INACTIVE)
        self.assertEqual(collection.pubnotes, [])
        self.assertEqual(collection.analyses, [])
        self.assertEqual(collection.unaccounted, [])

    def test_numbered_note_without_url_is_reported_as_unaccounted(self):
        for cls in (ConfNote, PubNote):
            with self.subTest(cls=cls), self.assertLogs(level="ERROR") as logs:
                entry = publication(cls, **{"Final URL": ""})
            self.assertIn("no final URL", logs.output[0])
            collection = registry(entry)
            self.assertEqual(entry.pub_state, State.UNKNOWN)
            self.assertEqual(collection.unaccounted, [entry])
            self.assertEqual(
                collection.analyses + collection.confnotes + collection.pubnotes, []
            )


class RegistryRoundTripTests(unittest.TestCase):
    def test_inherited_json_loader_recomputes_new_derived_fields(self):
        @define
        class ExtendedAnalysis(Analysis):
            summary: str = field(init=False)

            def __attrs_post_init__(self):
                super().__attrs_post_init__()
                self.summary = f"{self.ref_code}: {self.status}"

        original = analysis()
        payload = asdict(original) | {"summary": "stale"}
        restored = ExtendedAnalysis.from_json(payload)
        self.assertEqual(restored.summary, f"{original.ref_code}: {original.status}")
        self.assertEqual(payload["summary"], "stale")
        self.assertEqual(restored.pub_state, original.pub_state)

    def test_model_loaders_reject_unknown_fields_without_mutating_payload(self):
        for entry in (
            analysis(),
            publication(Paper),
            publication(ConfNote),
            publication(PubNote),
        ):
            with self.subTest(kind=type(entry).__name__):
                payload = asdict(entry) | {"unexpected_field": "not part of the model"}
                original_payload = payload.copy()
                with self.assertRaisesRegex(TypeError, "unexpected_field"):
                    type(entry).from_json(payload)
                self.assertEqual(payload, original_payload)

    def test_legacy_snapshot_without_threshold_keeps_the_default_cutoff(self):
        older = publication(
            Paper,
            "TOPQ-2099-01",
            **{"Publication Date": "2019-12-31", "arXiv Submission Date": "2019-01-01"},
        )
        recent = publication(Paper, "TOPQ-2099-02")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            registry(older, recent).store_json(path)
            payload = json.loads(path.read_text())
            del payload["threshold_year"]
            path.write_text(json.dumps(payload))
            restored = GlanceRegistry.from_json(path)
        self.assertEqual(restored.threshold_year, "2020")
        self.assertEqual(refs(restored.papers), {recent.ref_code})

    def test_all_entry_types_and_metadata_round_trip(self):
        entries = [
            analysis(),
            publication(Paper, "TOPQ-2099-02"),
            publication(ConfNote, "TOPQ-2099-03"),
            publication(PubNote, "TOPQ-2099-04"),
        ]
        original = registry(*entries, threshold="2022")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            original.store_json(path)
            restored = GlanceRegistry.from_json(path)
        self.assertEqual(restored.entries, original.entries)
        self.assertEqual(restored.threshold_year, "2022")
        self.assertEqual(restored.last_modified_time, "synthetic sync time")
        for entry in entries:
            self.assertIs(type(restored.get(entry.ref_code)), type(entry))
        for category in ("analyses", "papers", "confnotes", "pubnotes", "unaccounted"):
            self.assertEqual(getattr(restored, category), getattr(original, category))

    def test_loading_recomputes_derived_fields_without_changing_raw_statuses(self):
        original = registry(
            analysis(),
            publication(Paper, "TOPQ-2099-02"),
            publication(ConfNote, "TOPQ-2099-03"),
            publication(PubNote, "TOPQ-2099-04"),
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            original.store_json(path)
            payload = json.loads(path.read_text())
            for record in payload["entries"].values():
                record.update(
                    pub_state="STALE",
                    software_release="STALE",
                    glance_url_analysis="stale",
                )
                if record["_entrytype"] != "Analysis":
                    record["glance_url_publ"] = "stale"
                if record["_entrytype"] == "Paper":
                    record.update(
                        dois=["stale"],
                        journal_ref="stale",
                        journal_ref_corrections=["stale"],
                    )
            path.write_text(json.dumps(payload))
            with patch.dict(
                "analysis_lister.citation_store.Citations",
                {DOI: "Updated citation"},
            ):
                restored = GlanceRegistry.from_json(path)
        for ref, entry in restored.entries.items():
            self.assertEqual(entry.status, original.get(ref).status)
            self.assertEqual(entry.pub_state, original.get(ref).pub_state)
            self.assertEqual(entry.software_release, SoftwareRelease.R25)
            self.assertEqual(
                entry.glance_url_analysis, original.get(ref).glance_url_analysis
            )
            self.assertEqual(entry.glance_url_publ, original.get(ref).glance_url_publ)
        paper = restored.get("TOPQ-2099-02")
        self.assertEqual(paper.status_paper, original.get(paper.ref_code).status_paper)
        self.assertEqual(paper.dois, [DOI])
        self.assertEqual(paper.journal_ref, "Updated citation")
        self.assertEqual(paper.journal_ref_corrections, [])


if __name__ == "__main__":
    unittest.main()
