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


class EnrichmentRulesTests(unittest.TestCase):
    def enrich(self, collection, cls, **changes):
        key, prefix = (
            ("Reference Code", "")
            if cls is Paper
            else ("Temporary Reference Code", "CONF-" if cls is ConfNote else "PUB-")
        )
        return collection.enrich(
            [publication_row(cls, **changes)], cls, key=key, prefix=prefix
        )

    def test_paper_wins_over_confnote_in_both_enrichment_orders(self):
        for order in ((Paper, ConfNote), (ConfNote, Paper)):
            with self.subTest(order=order):
                base = analysis(status=FINISHED)
                collection = registry(base)
                self.assertEqual(self.enrich(collection, order[0]), (1, 0))
                with self.assertLogs(level="DEBUG") as logs:
                    counts = self.enrich(collection, order[1])
                self.assertEqual(counts, (1 if order[1] is Paper else 0, 0))
                self.assertIn("keeping the paper", "\n".join(logs.output))
                entry = collection.get(base.ref_code)
                self.assertIsInstance(entry, Paper)
                self.assertEqual(entry.arxiv_number, "arXiv:2301.00001")
                self.assertEqual(entry.dois, [DOI])
                self.assertEqual(entry.contacts, "Current Contact")
                self.assertEqual(entry.editorial_board, base.editorial_board)
                self.assertEqual(entry.supporting_docs, base.supporting_docs)
                self.assertEqual(refs(collection.papers), {base.ref_code})
                self.assertEqual(collection.confnotes, [])

    def test_other_cross_type_collisions_keep_existing_record_and_warn(self):
        for first, second in (
            (Paper, PubNote),
            (PubNote, Paper),
            (ConfNote, PubNote),
            (PubNote, ConfNote),
        ):
            with self.subTest(first=first, second=second):
                collection = registry(analysis(status=FINISHED))
                self.enrich(collection, first)
                original = collection.get("TOPQ-2099-01")
                with self.assertLogs(level="WARNING") as logs:
                    self.assertEqual(self.enrich(collection, second), (0, 0))
                self.assertIs(collection.get(original.ref_code), original)
                self.assertIn(f"keeping the {first.__name__}", logs.output[0])
                self.assertIn(original.ref_code, logs.output[0])

    def test_repeated_enrichment_keeps_first_publication(self):
        for cls in (Paper, ConfNote, PubNote):
            with self.subTest(cls=cls):
                collection = registry(analysis(status=FINISHED))
                self.enrich(collection, cls)
                original = collection.get("TOPQ-2099-01")
                with self.assertLogs(level="WARNING") as logs:
                    self.assertEqual(self.enrich(collection, cls), (0, 0))
                self.assertIs(collection.get(original.ref_code), original)
                self.assertIn("listed twice", logs.output[0])

    def test_pub_matching_requires_identical_nonempty_short_title(self):
        for title in (
            "Synthetic title",
            "Different title",
            "synthetic title",
            "Synthetic title ",
            "",
        ):
            with self.subTest(title=title):
                base = analysis(status=FINISHED)
                collection = registry(base)
                counts = self.enrich(collection, PubNote, **{"Short Title": title})
                matches = title == "Synthetic title"
                self.assertEqual(counts, (int(matches), int(not matches)))
                if matches:
                    self.assertIsInstance(collection.get(base.ref_code), PubNote)
                else:
                    self.assertIs(collection.get(base.ref_code), base)
        collection = registry(analysis(status=FINISHED, **{"Short Title": ""}))
        self.assertEqual(
            self.enrich(collection, PubNote, **{"Short Title": ""}), (0, 1)
        )

    def test_pub_matching_uses_original_titles_before_display_escaping(self):
        base = analysis(status=FINISHED, **{"Short Title": "Synthetic | title"})
        collection = registry(base)
        row = publication_row(PubNote, **{"Short Title": "Synthetic | title"})
        self.assertEqual(
            collection.enrich(
                [row],
                PubNote,
                key="Temporary Reference Code",
                prefix="PUB-",
                analysis_short_titles={base.ref_code: "Synthetic | title"},
            ),
            (1, 0),
        )

    def test_unmatched_publication_does_not_create_an_analysis(self):
        collection = registry(analysis("TOPQ-2099-99", FINISHED))
        self.assertEqual(self.enrich(collection, Paper), (0, 1))
        self.assertEqual(set(collection.entries), {"TOPQ-2099-99"})
        self.assertEqual(collection.papers, [])


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
