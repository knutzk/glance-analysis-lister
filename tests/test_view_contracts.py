# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Stable prepared contracts preserve evidence and distinguish missing policy."""

import unittest
from pathlib import Path

from attrs.exceptions import FrozenInstanceError

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.models import (
    NoteDetails,
    PublicationDetails,
    PublicationLink,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy


class PreparedContractTests(unittest.TestCase):
    def test_explicit_policy_is_immutable_and_owns_its_lists(self):
        groups = [" DEMO ", "DEMO"]
        policy = PublicationPolicy(groups=groups, title=" Invented title ")
        groups.append("OTHER")
        self.assertEqual(policy.groups, ("DEMO",))
        self.assertEqual(policy.title, "Invented title")
        with self.assertRaises(FrozenInstanceError):
            policy.title = "Changed"
        self.assertIsNone(GroupProfile("DEMO").publication_policy)
        self.assertIsNotNone(
            GroupProfile(
                "DEMO", publication_policy=PublicationPolicy()
            ).publication_policy
        )
        for values in ("DEMO", [None], [""]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                PublicationPolicy(groups=values)
        with self.assertRaises(ValueError):
            GroupProfile("DEMO", publication_policy={})

    def test_prepared_details_are_typed_but_source_evidence_stays_serializable(self):
        registry = CuratedRegistry.from_json(
            Path(__file__).resolve().parents[1] / "examples/synthetic_registry.json"
        )
        view = prepare_group(registry, GroupProfile("DEMO"))
        for row in view.archive:
            self.assertIsInstance(row.details, PublicationDetails)
            self.assertIsInstance(row.details.contacts, tuple)
            for link in row.details.publication_records:
                self.assertIsInstance(link, PublicationLink)
            note = row.details.conf_note or row.details.pub_note
            if note:
                self.assertIsInstance(note, NoteDetails)
            self.assertIsInstance(row.provenance["details"]["value"], dict)
