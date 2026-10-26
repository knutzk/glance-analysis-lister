# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""API-only construction requires no CSV inputs or network calls."""

import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from view_fixtures import api_fixture

from analysis_lister.registry import CuratedRegistry
from analysis_lister.registry.builder import build_registry
from analysis_lister.registry.fields import count_fields
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy
from analysis_lister.views.report import build_report

MAPPING = {
    "9999999": {
        "identifier": "ATL-PHYS-PUB-2099-001",
        "source_url": "https://cds.cern.ch/record/9999999",
    }
}


class ApiOnlyRegistryTests(unittest.TestCase):
    def test_offline_builder_uses_dictionary_and_reports_unresolved_releases(self):
        api = api_fixture()
        for resource in ("analyses", "papers", "confnotes", "pubnotes"):
            api[resource][0]["groups"] = {"leadingGroup": {"name": "DEMO"}}
        note = api["pubnotes"][0]
        note["status"] = "Phase 1 Finished"
        note["phase1"] = {
            "releaseDate": "2099-01-01",
            "draftCdsUrl": "https://cds.cern.ch/record/9999999",
        }
        original = copy.deepcopy(api)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, mapping = (
                root / "api.json",
                root / "curated.json",
                root / "identifiers.json",
            )
            source.write_text(json.dumps(api))
            mapping.write_text(json.dumps(MAPPING))
            with patch("requests.get", side_effect=AssertionError("no network")):
                build_registry(source, output, pubnote_identifiers=mapping)
            data = json.loads(output.read_text())
            self.assertEqual(json.loads(source.read_text()), original)
            self.assertEqual(
                data["pubnotes"][0]["gal_finalReferenceCode"], "ATL-PHYS-PUB-2099-001"
            )
            self.assertNotIn("gal_internalNoteEditors", data["analyses"][0])
            self.assertNotIn("gal_currentPaperDraft", data["papers"][0])
            self.assertNotIn("html_source", data["gal_curation"])
            self.assertNotIn("supplement_fields", data["gal_curation"])
            mapping.write_text("{}")
            with self.assertLogs(
                "analysis_lister.registry.enrichment", level="WARNING"
            ):
                build_registry(source, output, pubnote_identifiers=mapping)
            data = json.loads(output.read_text())
            view = prepare_group(
                CuratedRegistry(data),
                GroupProfile(
                    "DEMO", publication_policy=PublicationPolicy(groups=("DEMO",))
                ),
            )
            report = build_report(view, output, output.read_bytes())
            diagnostic = next(
                row
                for row in report["records_with_diagnostics"]
                if row["resource"] == "pubnotes"
            )
            self.assertTrue(
                any(
                    issue["kind"] == "public_identifier"
                    for issue in diagnostic["issues"]
                )
            )
            before = output.read_bytes()
            with self.assertRaisesRegex(ValueError, "overwrite an input"):
                build_registry(source, mapping, pubnote_identifiers=mapping)
            self.assertEqual(output.read_bytes(), before)

    def test_build_logging_explains_offline_inputs_and_does_not_claim_failed_publication(
        self,
    ):
        api = api_fixture()
        api["analyses"][0]["shortTitle"] = "Invented μ title"
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, mapping, citations = (
                root / "api.json",
                root / "curated.json",
                root / "identifiers.json",
                root / "citations.json",
            )
            source.write_text(json.dumps(api, ensure_ascii=False))
            mapping.write_text(json.dumps(MAPPING))
            citations.write_text("{}")
            with self.assertLogs("analysis_lister", level="INFO") as captured:
                build_registry(
                    source, output, pubnote_identifiers=mapping, doi_cache=citations
                )
            messages = "\n".join(captured.output)
            for expected in (
                "API-only registry build",
                "offline; no HTML or external requests",
                str(source),
                str(output),
                str(mapping),
                str(citations),
                "Loaded 0 DOI entries and 1 CDS-to-PUB",
                "Curating analyses: 1 API records",
                "Curated papers: 1 records",
                "Validating complete curated registry",
                "DOI summary",
                "Published curated registry",
            ):
                self.assertIn(expected, messages)
            result = json.loads(output.read_text())
            for resource in ("analyses", "papers", "confnotes", "pubnotes"):
                self.assertIn(
                    f"Field selection {resource}: retained {count_fields(result[resource])} of ",
                    messages,
                )
            input_size, output_size = len(source.read_bytes()), len(output.read_bytes())
            self.assertIn(f"API input {input_size} bytes", messages)
            self.assertIn(f"curated output {output_size} bytes", messages)
            self.assertIn(f"{abs(input_size - output_size)} bytes ", messages)
            self.assertIn(
                "Counts include nested object keys after enrichment", messages
            )
            self.assertNotIn("Current Example", messages)
            self.assertNotIn("Invented μ title", messages)
            before = output.read_bytes()
            with (
                patch(
                    "analysis_lister.registry.builder.atomic_write_text",
                    side_effect=OSError("invented failure"),
                ),
                self.assertLogs("analysis_lister", level="INFO") as captured,
                self.assertRaises(OSError),
            ):
                build_registry(
                    source, output, pubnote_identifiers=mapping, doi_cache=citations
                )
            self.assertEqual(before, output.read_bytes())
            self.assertFalse(
                any("Registry file sizes:" in line for line in captured.output)
            )
            self.assertTrue(any("Count check" in line for line in captured.output))
            self.assertFalse(
                any("Published curated registry:" in line for line in captured.output)
            )
