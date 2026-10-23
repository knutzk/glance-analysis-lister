# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Curated access and package boundaries, using independently invented records."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from view_fixtures import api_fixture

from analysis_lister.registry import CuratedRegistry
from analysis_lister.registry.enrichment import curate

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    data = curate(api_fixture(), {})
    analysis = data["analyses"][0]
    analysis["relatedPublications"] = []
    for resource, kind in (
        ("papers", "Paper"),
        ("confnotes", "CONF note"),
        ("pubnotes", "PUB note"),
    ):
        publication = data[resource][0]
        field = "referenceCode" if resource == "papers" else "temporaryReferenceCode"
        analysis.setdefault("relatedPublications", []).append(
            {"referenceCode": publication[field], "type": kind}
        )
        publication["relatedAnalysis"] = {
            "referenceCode": analysis["referenceCode"],
            "type": "Analysis",
        }
    return data


class CuratedReaderTests(unittest.TestCase):
    def test_native_identifiers_and_explicit_links_are_resolved_without_merging(self):
        data = snapshot()
        reader = CuratedRegistry(data)
        analysis = reader.get("analyses", "ANA-DEMO-2099-01")
        for resource, link in zip(
            ("papers", "confnotes", "pubnotes"),
            analysis["relatedPublications"],
            strict=True,
        ):
            record = reader.resolve_link(link)
            self.assertEqual(record, reader.records(resource)[0])
            self.assertEqual(reader.resolve_link(record["relatedAnalysis"]), analysis)
        self.assertIsNone(reader.get("papers", "DEMO-2099-404"))
        self.assertIsNone(
            reader.resolve_link({"type": "Paper", "referenceCode": "DEMO-2099-404"})
        )
        self.assertEqual(reader.metadata["counts"], data["counts"])
        self.assertNotIn("analyses", reader.metadata)
        for invalid in (
            None,
            {},
            {"type": []},
            {"type": "Unknown", "referenceCode": "DEMO"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reader.resolve_link(invalid)
        with self.assertRaises(KeyError):
            reader.records("unknown")

    def test_snapshot_and_returned_records_cannot_invalidate_indexes(self):
        data = snapshot()
        before = copy.deepcopy(data)
        reader = CuratedRegistry(data)
        data["analyses"][0]["referenceCode"] = "changed"
        record = reader.get("analyses", "ANA-DEMO-2099-01")
        record["referenceCode"] = "changed again"
        reader.records("papers")[0]["metadata"].clear()
        reader.metadata["counts"].clear()
        self.assertEqual(
            reader.get("analyses", "ANA-DEMO-2099-01"), before["analyses"][0]
        )
        self.assertEqual(reader.records("papers")[0], before["papers"][0])
        self.assertEqual(reader.metadata["counts"], before["counts"])

    def test_file_loading_validates_schema_and_identifiers(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "curated.json"
            data = snapshot()
            path.write_text(json.dumps(data))
            self.assertEqual(
                CuratedRegistry.from_json(path).metadata["counts"], data["counts"]
            )
            data["papers"].append(copy.deepcopy(data["papers"][0]))
            with self.assertRaisesRegex(ValueError, "identifiers"):
                CuratedRegistry(data)
            with self.assertRaisesRegex(ValueError, "supported curated"):
                CuratedRegistry({"entries": {}})
            old = snapshot()
            old["schema_version"] = 1
            for resource in old["counts"]:
                for record in old[resource]:
                    for field in ("analysisContacts", "contactEditors"):
                        record[field] = record.pop("gal_" + field)
            with self.assertRaisesRegex(ValueError, "supported curated"):
                CuratedRegistry(old)

    def test_reader_import_does_not_import_construction_or_downloaders(self):
        code = """
import sys
from analysis_lister.registry import CuratedRegistry
assert not any(name.startswith(("analysis_lister.glance", "analysis_lister.downloaders"))
               for name in sys.modules)
assert "analysis_lister.registry.builder" not in sys.modules
assert "analysis_lister.registry.enrichment" not in sys.modules
assert "requests" not in sys.modules
assert "stare" not in sys.modules
assert "selenium" not in sys.modules
"""
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
