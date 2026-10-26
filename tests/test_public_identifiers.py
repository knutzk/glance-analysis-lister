# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline identifier recovery uses only public URLs and a validated dictionary."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister.registry.public_identifiers import (
    cds_record_id,
    default_identifiers_path,
    enrich_public_identifiers,
    load_identifiers,
)

MAPPING = {
    "9999999": {
        "identifier": "ATL-PHYS-PUB-2099-001",
        "source_url": "https://cds.cern.ch/record/9999999",
    }
}


class PublicIdentifierTests(unittest.TestCase):
    def test_native_identifier_wins_and_url_extraction_is_unambiguous(self):
        for resource, identifier in (
            ("pubnotes", "ATL-SOFT-PUB-2099-001"),
            ("confnotes", "ATLAS-CONF-2099-001"),
        ):
            record = {
                "finalReferenceCode": identifier,
                "phase1": {
                    "publicWebPageUrlForFiguresAndTables": "https://example.test/ATL-PHYS-PUB-2099-002"
                },
            }
            self.assertEqual(
                enrich_public_identifiers(record, resource, MAPPING)["source"], "api"
            )
            self.assertNotIn("gal_finalReferenceCode", record)
            record["finalReferenceCode"] = "temporary placeholder"
            record["phase1"]["publicWebPageUrlForFiguresAndTables"] = (
                "https://example.test/" + identifier + "/"
            )
            self.assertEqual(
                enrich_public_identifiers(record, resource, MAPPING)["source"],
                "api-public-url",
            )
            self.assertEqual(record["gal_finalReferenceCode"], identifier)
        record = {
            "status": "Phase 1 Finished",
            "phase1": {
                "publicWebPageUrlForFiguresAndTables": "https://example.test/ATL-PHYS-PUB-2099-001/ATL-PHYS-PUB-2099-002"
            },
        }
        self.assertEqual(
            enrich_public_identifiers(record, "pubnotes", MAPPING)["source"],
            "unresolved",
        )
        self.assertNotIn("gal_finalReferenceCode", record)

    def test_cds_aliases_and_draft_link_fallback_do_not_make_requests(self):
        for url in (
            "https://cds.cern.ch/record/9999999",
            "http://cdsweb.cern.ch/record/9999999/?ln=en",
        ):
            self.assertEqual(cds_record_id(url), "9999999")
            record = {"phase1": {"publicWebPageUrlForFiguresAndTables": url}}
            self.assertEqual(
                enrich_public_identifiers(record, "pubnotes", MAPPING)["cds_record"],
                "9999999",
            )
        for bad in (
            None,
            "None",
            "https://example.test/record/9999999",
            "https://[",
            "javascript:alert(1)",
        ):
            self.assertIsNone(cds_record_id(bad))
        record = {
            "phase1": {
                "publicWebPageUrlForFiguresAndTables": "None",
                "draftCdsUrl": "https://cds.cern.ch/record/9999999",
            }
        }
        with patch("requests.get", side_effect=AssertionError("no network")):
            evidence = enrich_public_identifiers(record, "pubnotes", MAPPING)
        self.assertEqual(evidence["api_field"], "phase1.draftCdsUrl")
        self.assertEqual(record["gal_finalReferenceCode"], "ATL-PHYS-PUB-2099-001")

    def test_published_paper_links_are_explicitly_derived_without_testing_availability(
        self,
    ):
        record = {
            "referenceCode": "DEMO-2099-01",
            "status": "Publication Phase Finished",
        }
        evidence = enrich_public_identifiers(record, "papers", {})
        self.assertEqual(
            record["gal_figuresUrl"],
            "https://atlas.web.cern.ch/Atlas/GROUPS/PHYSICS/PAPERS/DEMO-2099-01/",
        )
        self.assertFalse(evidence["availability_checked"])
        pending = {"referenceCode": "DEMO-2099-02", "status": "Phase 1 Active"}
        self.assertIsNone(enrich_public_identifiers(pending, "papers", {}))

    def test_dictionary_rejects_duplicates_private_fields_and_bad_values(self):
        self.assertTrue(load_identifiers(default_identifiers_path()))
        for data in (
            '{"1": {}, "1": {}}',
            '{"1": {"identifier": null, "source_url": "bad"}}',
            '{"ANA-DEMO-2099-01": {}}',
        ):
            with TemporaryDirectory() as directory:
                path = Path(directory) / "identifiers.json"
                path.write_text(data)
                with self.assertRaises(ValueError):
                    load_identifiers(path)
