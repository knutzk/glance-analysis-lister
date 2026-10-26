# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Record selection keeps view behavior while excluding unused API payloads."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from view_fixtures import api_fixture

from analysis_lister.registry import CuratedRegistry
from analysis_lister.registry.enrichment import curate
from analysis_lister.registry.fields import RECORD_FIELDS, select_fields
from analysis_lister.views.markdown.pages import (
    confnotes_page,
    ongoing_page,
    papers_page,
    pubnotes_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.publication_states import PAPER_MILESTONES


class RegistryFieldTests(unittest.TestCase):
    def test_future_and_nested_unused_fields_are_not_persisted(self):
        api = api_fixture()
        for resource in RECORD_FIELDS:
            record = api[resource][0]
            record["futureField"] = {"private": "unused"}
            record["metadata"]["unused"] = "unused"
            record["documentation"]["supportingInternalDocuments"] = [
                {
                    "label": "Supporting note",
                    "url": "https://example.test/note",
                    "id": 123,
                }
            ]
        paper = api["papers"][0]
        paper["publicationPhase"] = {
            "finalJournalPublicationUrls": [{"url": "https://doi.org/10.9999/demo"}],
        }
        result = curate(
            api,
            citations={
                "10.9999/demo": {
                    "citation": "Invented citation",
                    "source": "manual",
                    "material": "publication",
                },
            },
        )
        for resource in RECORD_FIELDS:
            record = result[resource][0]
            self.assertNotIn("futureField", record)
            self.assertNotIn("unused", record["metadata"])
            self.assertEqual(
                record["documentation"]["supportingInternalDocuments"],
                [
                    {"label": "Supporting note", "url": "https://example.test/note"},
                ],
            )
        self.assertEqual(
            result["papers"][0]["publicationPhase"],
            {
                "gal_dois": [
                    {
                        "doi": "10.9999/demo",
                        "url": "https://doi.org/10.9999/demo",
                        "citation": "Invented citation",
                    }
                ],
            },
        )
        self.assertEqual(result["gal_curation"]["doi_statistics"]["resolved"], 1)

    def test_every_dated_paper_milestone_is_retained(self):
        for phase, events in PAPER_MILESTONES.items():
            for field, _ in events:
                with self.subTest(phase=phase, field=field):
                    self.assertIn(field, RECORD_FIELDS["papers"][phase])

    def test_projection_preserves_missing_null_and_string_list_values(self):
        record = {
            "metadata": {"mvaMlTools": ["Tool", {"name": "Other", "id": 1}]},
            "phase1": None,
        }
        before = copy.deepcopy(record)
        self.assertEqual(
            select_fields(record, RECORD_FIELDS["pubnotes"]),
            {
                "metadata": {"mvaMlTools": ["Tool", {"name": "Other"}]},
                "phase1": None,
            },
        )
        self.assertEqual(record, before)

    def test_full_and_trimmed_records_render_identically(self):
        data = json.loads(
            (
                Path(__file__).resolve().parents[1] / "examples/synthetic_registry.json"
            ).read_text()
        )
        # Populate every consumed milestone and optional note metadata, not just
        # the sparse values in the distributed example.
        for resource in RECORD_FIELDS:
            for record in data[resource]:
                record["unusedFutureField"] = "discard me"
                record.setdefault("metadata", {}).update(
                    {
                        "gal_keywords": ["Invented keyword"],
                        "gal_triggers": ["Invented trigger"],
                        "gal_statisticalTools": ["Invented tool"],
                        "mvaMlTools": [{"name": "Invented ML tool", "id": 123}],
                        "collisions": [
                            {
                                "year": "2099",
                                "run": "3",
                                "type": "pp",
                                "ecmValue": "13",
                                "ecmUnit": "TeV",
                                "luminosityValue": "100",
                                "luminosityUnit": "fb-1",
                                "id": 456,
                            }
                        ],
                    }
                )
                if resource == "papers":
                    for phase, events in PAPER_MILESTONES.items():
                        for field, _ in events:
                            record.setdefault(phase, {})[field] = "2099-02-01"
        trimmed = copy.deepcopy(data)
        for resource in RECORD_FIELDS:
            trimmed[resource] = [
                select_fields(record, RECORD_FIELDS[resource])
                for record in data[resource]
            ]
        before = prepare_group(CuratedRegistry(data), GroupProfile("DEMO"))
        after = prepare_group(CuratedRegistry(trimmed), GroupProfile("DEMO"))
        for render in (ongoing_page, papers_page, confnotes_page, pubnotes_page):
            with self.subTest(renderer=render.__name__):
                self.assertEqual(render(before), render(after))
        self.assertEqual(before.controls, after.controls)
        self.assertEqual(
            [row.metadata for row in before.publications],
            [row.metadata for row in after.publications],
        )
        self.assertLess(len(json.dumps(trimmed)), len(json.dumps(data)))

    def test_builder_projects_after_all_enrichment(self):
        api = api_fixture()
        api["confnotes"][0]["phase1"]["publicWebPageUrlForFiguresAndTables"] = (
            "https://example.test/ATLAS-CONF-2099-001"
        )
        with patch(
            "analysis_lister.registry.enrichment.select_fields",
            side_effect=lambda value, fields: value,
        ):
            full = curate(api)
        trimmed = curate(api)
        for resource in RECORD_FIELDS:
            self.assertEqual(
                trimmed[resource],
                [
                    select_fields(record, RECORD_FIELDS[resource])
                    for record in full[resource]
                ],
            )
        self.assertEqual(
            trimmed["confnotes"][0]["gal_finalReferenceCode"], "ATLAS-CONF-2099-001"
        )
