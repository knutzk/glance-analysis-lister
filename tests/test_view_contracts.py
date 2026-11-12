# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Stable prepared contracts preserve evidence and distinguish missing policy."""

import subprocess
import sys
import unittest
from pathlib import Path

from attrs.exceptions import FrozenInstanceError
from view_fixtures import analysis, publication, snapshot

from grove.registry import CuratedRegistry
from grove.views.models import (
    NoteDetails,
    PublicationDetails,
    PublicationLink,
)
from grove.views.prepare import prepare_group
from grove.views.profiles import GroupProfile, PublicationPolicy


class PreparedContractTests(unittest.TestCase):
    def test_public_preparation_works_without_io_or_renderer_imports(self):
        code = """
import sys
from grove.registry import CuratedRegistry, RESOURCES, SCHEMA, validate_registry
from grove.views.curation import load_publication_policy
from grove.views.prepare import prepare_group
from grove.views.profiles import GroupProfile, PublicationPolicy

registry = CuratedRegistry.from_json("examples/synthetic_registry.json")
policy = load_publication_policy("examples/demo/publication-curation.toml", "DEMO")
before = {resource: registry.records(resource) for resource in RESOURCES}
assert registry.metadata["schema"] == SCHEMA
assert "schema_version" not in registry.metadata
validate_registry({**registry.metadata, **{key: list(value) for key, value in before.items()}})

def reject_io(event, args):
    if event in {"open", "socket.connect", "socket.getaddrinfo"}:
        raise AssertionError(f"Unexpected I/O during preparation: {event}")

sys.addaudithook(reject_io)
view = prepare_group(registry, GroupProfile("DEMO", publication_policy=policy))
assert len(view.ongoing) == 4
assert len(view.archive) == 12
assert {resource: registry.records(resource) for resource in RESOURCES} == before
assert all(isinstance(row.metadata["text"], str) for row in (*view.ongoing, *view.archive))
empty = prepare_group(registry, GroupProfile("DEMO", publication_policy=PublicationPolicy()))
assert len(empty.ongoing) == 4 and empty.archive == ()
assert not any(name.startswith(("grove.views.markdown", "grove.downloaders"))
               for name in sys.modules)
assert not {"requests", "stare", "selenium"}.intersection(sys.modules)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_record_metadata_is_independent_of_page_control_choices(self):
        active = analysis(1)
        active["gal_groups"]["leadingSubgroup"] = "DEMO-Active"
        active["metadata"] = {
            "gal_keywords": ["Invented keyword"],
            "gal_triggers": ["Invented trigger"],
            "gal_statisticalTools": ["Invented tool"],
        }
        historical = publication(1)
        historical["gal_groups"]["leadingSubgroup"] = "DEMO-Historical"
        view = prepare_group(
            CuratedRegistry(snapshot(active, papers=(historical,))),
            GroupProfile("DEMO"),
        )
        row = view.ongoing[0]
        for value in ("Invented keyword", "Invented trigger", "Invented tool"):
            self.assertIn(value, row.metadata["text"])
        self.assertEqual(row.metadata["triggers"], ["Invented trigger"])
        self.assertEqual(
            view.controls["ongoing"]["subgroups"], (("DEMO-Active", "DEMO-Active"),)
        )
        self.assertEqual(set(view.controls["ongoing"]), {"subgroups", "sort"})
        self.assertEqual(set(view.controls["papers"]), {"publication_status"})
        for resource in ("confnotes", "pubnotes"):
            self.assertEqual(set(view.controls[resource]), {"supersession"})

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

    def test_documented_display_values_can_be_consumed_without_internal_models(self):
        registry = CuratedRegistry.from_json(
            Path(__file__).resolve().parents[1] / "examples/synthetic_registry.json"
        )
        view = prepare_group(registry, GroupProfile("DEMO"))
        for row in (*view.ongoing, *view.archive):
            with self.subTest(reference=row.reference):
                self.assertIsInstance(row.title, str)
                self.assertIsInstance(row.metadata["text"], str)
                for field in ("subgroups", "keywords", "triggers", "statistical_tools"):
                    self.assertIsInstance(row.metadata[field], list)
                    self.assertTrue(
                        all(isinstance(value, str) for value in row.metadata[field])
                    )
                self.assertIsInstance(
                    row.metadata["leading_subgroup"], (str, type(None))
                )
                with self.assertRaises(FrozenInstanceError):
                    row.title = "Changed"
        for row in view.archive:
            self.assertIsInstance(row.date, (str, type(None)))
            self.assertIsInstance(row.details.cite_as, tuple)
            self.assertTrue(all(isinstance(line, str) for line in row.details.cite_as))
            self.assertEqual(bool(row.details.cite_as), row.resource == "papers")
            for link in (*row.details.publication_records, *row.details.links):
                self.assertIsInstance(link.label, str)
                self.assertIsInstance(link.url, (str, type(None)))
            for note in (row.details.conf_note, row.details.pub_note):
                if note is None:
                    continue
                self.assertIsInstance(note.superseded, bool)
                for role in note.people:
                    self.assertIsInstance(role.label, str)
                    self.assertIsInstance(role.names, tuple)
                for tag in note.tags:
                    self.assertIsInstance(tag.label, str)
                    self.assertIsInstance(tag.values, tuple)
