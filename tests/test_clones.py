# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Synthetic manual clone lineage and publication precedence."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_domain_rules import (
    ACTIVE,
    FINISHED,
    ConfNote,
    Paper,
    analysis,
    publication,
    registry,
)

from analysis_lister.glance.enums import PublicationState as State
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.lookup_dicts.clones import Clones

ORIGIN = "DEMO-2099-01"
CHILD = "DEMO-2099-02"
SIBLING = "DEMO-2099-03"


class CloneTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(Clones, {}, clear=True))

    def link(self, origin, *children):
        Clones.update(dict.fromkeys(children, origin))

    def test_conf_is_superseded_by_descendant_paper_and_recomputed_on_load(self):
        conf = publication(ConfNote, ORIGIN)
        paper = publication(Paper, CHILD)
        self.link(ORIGIN, CHILD)
        collection = registry(conf, paper)
        self.assertEqual(collection.confnotes, [])
        self.assertEqual(collection.papers, [paper])
        self.assertTrue(collection.is_clone_excluded(ORIGIN))
        self.assertEqual(conf.pub_state, State.PUBLISHED)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            collection.store_json(path)
            raw = json.loads(path.read_text())
            for entry in raw["entries"].values():
                self.assertFalse(
                    {"cloned_from", "cloned_into", "clone_superseded_by"} & entry.keys()
                )
            restored = GlanceRegistry.from_json(path)
            self.assertEqual(restored.confnotes, [])
            self.assertTrue(restored.is_clone_excluded(ORIGIN))
            Clones.clear()
            restored = GlanceRegistry.from_json(path)
            self.assertEqual([entry.ref_code for entry in restored.confnotes], [ORIGIN])

    def test_review_paper_supersedes_conf_but_closed_paper_does_not(self):
        for status, expected in (
            (" Phase 1 is  Active ", []),
            (" Publication is  Closed ", [ORIGIN]),
        ):
            conf = publication(ConfNote, ORIGIN)
            paper = publication(
                Paper,
                CHILD,
                **{
                    "Status": status,
                    "arXiv Submission Date": "",
                    "Publication Date": "",
                },
            )
            self.link(ORIGIN, CHILD)
            collection = registry(conf, paper)
            self.assertEqual(
                [entry.ref_code for entry in collection.confnotes], expected
            )

    def test_transitive_links_missing_entries_and_multiple_papers(self):
        conf = publication(ConfNote, ORIGIN)
        middle = analysis(SIBLING, FINISHED)
        paper = publication(Paper, CHILD)
        second = publication(Paper, "DEMO-2099-04")
        self.link(ORIGIN, SIBLING, "DEMO-2099-99")
        self.link(SIBLING, CHILD, second.ref_code)
        collection = registry(conf, middle, paper, second)
        self.assertEqual(collection.confnotes, [])
        self.assertEqual(collection.papers, [paper, second])
        self.assertEqual(collection.unaccounted, [])

    def test_distinct_sibling_conf_and_active_clone_are_preserved(self):
        origin = analysis(ORIGIN, FINISHED)
        conf = publication(ConfNote, CHILD)
        paper = publication(Paper, SIBLING)
        active = analysis("DEMO-2099-04", ACTIVE)
        self.link(ORIGIN, CHILD, SIBLING, active.ref_code)
        collection = registry(origin, conf, paper, active)
        self.assertEqual(collection.confnotes, [conf])
        self.assertEqual(collection.analyses, [active])
        self.assertEqual(collection.unaccounted, [])

    def test_missing_clone_does_not_hide_conf_or_unattached_analysis(self):
        conf = publication(ConfNote, ORIGIN)
        bare = analysis(CHILD, FINISHED)
        self.link(ORIGIN, "DEMO-2099-99")
        collection = registry(conf, bare)
        self.assertEqual(collection.confnotes, [conf])
        self.assertEqual(collection.unaccounted, [bare])

    def test_finished_clone_with_closed_origin_is_ignored(self):
        self.link(ORIGIN, CHILD)
        origin = analysis(ORIGIN, " Analysis is  Closed ")
        clone = analysis(CHILD, FINISHED)
        collection = registry(origin, clone)
        self.assertEqual(collection.analyses, [])
        self.assertEqual(collection.unaccounted, [])
        self.assertEqual(set(collection.entries), {ORIGIN, CHILD})

    def test_paper_date_threshold_does_not_resurrect_superseded_conf(self):
        conf = publication(ConfNote, ORIGIN)
        paper = publication(Paper, CHILD, **{"Publication Date": "2019-07-01"})
        self.link(ORIGIN, CHILD)
        collection = registry(conf, paper, threshold="2020")
        self.assertEqual(collection.papers, [])
        self.assertEqual(collection.confnotes, [])

    def test_cycle_rejected(self):
        a, b = analysis(ORIGIN), analysis(CHILD)
        self.link(ORIGIN, CHILD)
        self.link(CHILD, ORIGIN)
        with self.assertRaisesRegex(ValueError, "Cycle"):
            registry(a, b)


if __name__ == "__main__":
    unittest.main()
