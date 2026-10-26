# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Fail when exercised view code reads fields the builder cannot retain.

Unlike output-only comparisons, guarded get() calls catch new fields even when
missing from fixtures. Rich and sparse records exercise nested paths as well.
"""

import copy
import unittest
from unittest.mock import patch

from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.registry.fields import RECORD_FIELDS
from analysis_lister.views.markdown.pages import (
    confnotes_page,
    ongoing_page,
    papers_page,
    pubnotes_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.publication_states import PAPER_MILESTONES


class GuardedRecord(dict):
    def __init__(self, value, fields, path):
        super().__init__(value)
        self.fields, self.path = fields, path

    def _check(self, key):
        if key not in self.fields:
            raise AssertionError(
                f"View reads unretained field: {self.path}.{key}; update registry/fields.py or remove this read"
            )

    def get(self, key, default=None):
        self._check(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self._check(key)
        return super().__getitem__(key)


def guard(value, fields, path):
    if fields is None:
        return value
    if isinstance(value, list):
        return [guard(item, fields, path + "[]") for item in value]
    if isinstance(value, dict):
        return GuardedRecord(
            {
                key: guard(item, fields.get(key), path + "." + key)
                for key, item in value.items()
            },
            fields,
            path,
        )
    return value


class AuditedRegistry(CuratedRegistry):
    def records(self, resource):
        return tuple(
            guard(record, RECORD_FIELDS[resource], resource)
            for record in super().records(resource)
        )


class RetainedFieldContractTests(unittest.TestCase):
    def test_guard_rejects_new_fields_even_when_the_fixture_lacks_them(self):
        record = guard(
            {"phase0": {"startDate": None}}, RECORD_FIELDS["analyses"], "analyses"
        )
        with self.assertRaisesRegex(AssertionError, r"analyses.phase0.newField"):
            record.get("phase0").get("newField")
        with self.assertRaisesRegex(AssertionError, r"analyses.newField"):
            record["newField"]
        self.assertIsNone(record.get("shortTitle"))

    def test_removing_a_consumed_field_fails_during_preparation(self):
        fields = copy.deepcopy(RECORD_FIELDS["analyses"])
        del fields["shortTitle"]
        with (
            patch.dict(RECORD_FIELDS, {"analyses": fields}),
            self.assertRaisesRegex(AssertionError, "analyses.shortTitle"),
        ):
            prepare_group(AuditedRegistry(snapshot(analysis(1))), GroupProfile("DEMO"))

    def test_preparation_and_all_renderers_read_only_retained_fields(self):
        for sparse in (False, True):
            for state in (
                "Phase 0 Active",
                "Phase 0 Finished",
                "Closed",
                "Created",
                "Unrecognised",
            ):
                with self.subTest(sparse=sparse, state=state):
                    source = analysis(1, status=state)
                    source["relatedPublications"] = [
                        {"type": "Paper", "referenceCode": "DEMO-2099-01"}
                    ]
                    papers = [
                        publication(
                            1,
                            related=source["referenceCode"],
                            status="Phase 2 Active",
                            date=None,
                        )
                    ]
                    papers.append(publication(2))
                    notes = {
                        resource: [
                            publication(
                                1,
                                resource=resource,
                                related=source["referenceCode"],
                                status="Phase 1 Finished",
                            )
                        ]
                        for resource in ("confnotes", "pubnotes")
                    }
                    for resource, records in (
                        ("analyses", [source]),
                        ("papers", papers),
                        *notes.items(),
                    ):
                        for record in records:
                            record["documentation"] = {
                                "supportingInternalDocuments": [
                                    {
                                        "label": "Invented document",
                                        "url": "https://example.test/doc",
                                    },
                                    {},
                                ]
                            }
                            record["metadata"] = {
                                "gal_keywords": ["Synthetic"],
                                "gal_triggers": ["Invented trigger"],
                                "gal_statisticalTools": ["Invented tool"],
                            }
                            if resource == "analyses":
                                record["phase0"]["gal_editorialBoardChairs"] = [
                                    "Invented Chair"
                                ]
                            elif resource == "papers":
                                for phase, events in PAPER_MILESTONES.items():
                                    record.setdefault(phase, {}).update(
                                        {field: "2099-01-01" for field, _ in events}
                                    )
                                record["publicationPhase"]["arXivUrls"] = [
                                    {
                                        "label": "Preprint",
                                        "url": "https://example.test/preprint",
                                    },
                                    {},
                                ]
                                record["phase1"]["gal_editorialBoardChairs"] = [
                                    "Invented Chair"
                                ]
                                if record["referenceCode"] == "DEMO-2099-01":
                                    record["publicationPhase"][
                                        "publishedOnlineDate"
                                    ] = None
                                    record["publicationPhase"][
                                        "arXivSubmissionDate"
                                    ] = None
                            else:
                                record["metadata"].update(
                                    {
                                        "mvaMlTools": [{"name": "Invented ML"}],
                                        "collisions": [
                                            {"year": "2099", "ecmValue": "13"}
                                        ],
                                    }
                                )
                                record["supersededBy"] = [
                                    {"type": "Paper", "referenceCode": "DEMO-2099-01"}
                                ]
                            if sparse:
                                for key in (
                                    "phase0",
                                    "phase1",
                                    "phase2",
                                    "publicationPhase",
                                    "metadata",
                                    "documentation",
                                ):
                                    if isinstance(record.get(key), dict):
                                        # Keep parents truthy to audit nested get() defaults.
                                        record[key] = {
                                            next(iter(record[key]), "unused"): None
                                        }
                    data = snapshot(source, papers=papers, **notes)
                    view = prepare_group(
                        AuditedRegistry(copy.deepcopy(data)), GroupProfile("DEMO")
                    )
                    for render in (
                        ongoing_page,
                        papers_page,
                        confnotes_page,
                        pubnotes_page,
                    ):
                        render(view)
