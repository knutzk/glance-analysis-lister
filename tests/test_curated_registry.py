# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Synthetic API-to-curated mapping and offline publication regressions."""

import copy
import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister import cli, registry
from analysis_lister.api import RESOURCES
from analysis_lister.download import download_tasks
from analysis_lister.retrieval import SCOPE_FILENAME, load_scope
from analysis_lister.storage import CSV_REFRESH_MARKER, SUPPLEMENT_MANIFEST


def person(first, last="Example", **roles):
    return {
        "firstName": first,
        "lastName": last,
        "cernCcid": "invented-id",
        "email": "invented@example.test",
        **roles,
    }


def api_fixture():
    records = {
        "analyses": {"referenceCode": "ANA-DEMO-2099-01"},
        "papers": {"referenceCode": "DEMO-2099-01"},
        "confnotes": {"temporaryReferenceCode": "CONF-DEMO-2099-01"},
        "pubnotes": {"temporaryReferenceCode": "PUB-DEMO-2099-01"},
    }
    source = {
        "schema": "glance-api-registry",
        "schema_version": 1,
        "fetched_at": "2099-01-10T12:00:00+00:00",
        "source": {
            "selection": "all-accessible",
            "base_url": "https://example.test/api",
        },
        "counts": dict.fromkeys(RESOURCES, 1),
    }
    for resource, record in records.items():
        record.update(
            {
                "analysisTeam": [
                    person("Current", isAnalysisContact=True, isContactEditor=True),
                    person("Current", isAnalysisContact=True),
                    person(
                        "Former",
                        isAnalysisContact=True,
                        analysisContactAssignment={"endDate": "2099-01-09"},
                    ),
                    person(
                        "Future",
                        isAnalysisContact=True,
                        analysisContactAssignment={"startDate": "2099-01-11"},
                    ),
                    person("Editor", isContactEditor=True),
                    person("Member"),
                ],
                "metadata": {
                    "keywords": [
                        {"name": "Keyword"},
                        {"name": "Keyword"},
                        {"name": "Other"},
                    ]
                },
                "phase0" if resource == "analyses" else "phase1": {
                    "editorialBoard": [
                        person("Chair", isChair=True),
                        person("Observer", isExOfficio=True),
                    ],
                    "signOffResponsible": person("Official"),
                    "startDate": "2099-01-01",
                },
                "relatedPublications": [
                    {"referenceCode": "DEMO-2099-01", "type": "Paper"}
                ],
                "documentation": {
                    "repositories": [{"url": "https://example.test/code"}]
                },
            }
        )
        source[resource] = [record]
    return source


class CuratedTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api_path = self.root / "api.json"
        self.csv_dir = self.root / "csv"
        self.csv_dir.mkdir()
        self.output = self.root / "nested" / "curated.json"
        self.api = api_fixture()
        self.api_path.write_text(json.dumps(self.api))
        tasks = download_tasks()
        (self.csv_dir / SUPPLEMENT_MANIFEST).write_text(
            json.dumps(
                {
                    "schema": "glance-csv-supplements",
                    "schema_version": 1,
                    "tables": {task.name: list(task.columns) for task in tasks},
                }
            )
        )
        (self.csv_dir / SCOPE_FILENAME).write_text(json.dumps(load_scope().metadata()))
        rows = {
            "analyses": [
                "ANA-DEMO-2099-01",
                "First Editor, Second Editor",
            ],
            "papers": [
                "DEMO-2099-01",
                "https://example.test/figures",
                "Invented draft",
            ],
            "pubnotes": ["PUB-DEMO-2099-01", "ATL-PHYS-PUB-2099-001"],
        }
        for task in tasks:
            with (self.csv_dir / task.csv_filename).open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerows([task.columns, rows[task.name]])

    def test_people_keywords_and_other_data_are_consolidated_without_mutating_input(
        self,
    ):
        before = copy.deepcopy(self.api)
        result = registry.curate(self.api, {})
        for resource in RESOURCES:
            record = result[resource][0]
            self.assertNotIn("analysisTeam", record)
            self.assertEqual(record["analysisContacts"], ["Current Example"])
            self.assertEqual(
                record["contactEditors"], ["Current Example", "Editor Example"]
            )
            phase = record.get("phase0") or record["phase1"]
            self.assertEqual(
                phase["editorialBoard"], ["Chair Example", "Observer Example"]
            )
            self.assertEqual(phase["editorialBoardChairs"], ["Chair Example"])
            self.assertEqual(phase["editorialBoardExOfficio"], ["Observer Example"])
            self.assertEqual(phase["signOffResponsible"], "Official Example")
            self.assertEqual(record["metadata"]["keywords"], ["Keyword", "Other"])
            self.assertEqual(
                record["relatedPublications"],
                self.api[resource][0]["relatedPublications"],
            )
            self.assertEqual(
                record["documentation"], self.api[resource][0]["documentation"]
            )
        self.assertNotIn("cernCcid", json.dumps(result))
        self.assertNotIn("@example.test", json.dumps(result))
        self.assertEqual(before, self.api)

    def test_complete_offline_cli_build_merges_supplements(self):
        with patch(
            "stare.auth.TokenManager", side_effect=AssertionError("No authentication")
        ):
            cli.main(
                [
                    "build-registry",
                    "--api-snapshot",
                    str(self.api_path),
                    "--csv-dir",
                    str(self.csv_dir),
                    "--output",
                    str(self.output),
                ]
            )
        result = json.loads(self.output.read_text())
        registry.validate_registry(result)
        self.assertNotIn("fullTitle", result["analyses"][0])
        self.assertEqual(
            result["analyses"][0]["internalNoteEditors"],
            ["First Editor", "Second Editor"],
        )
        self.assertEqual(
            result["papers"][0]["figuresUrl"], "https://example.test/figures"
        )
        self.assertNotIn("creationDate", result["pubnotes"][0])
        self.assertEqual(
            result["pubnotes"][0]["finalReferenceCode"], "ATL-PHYS-PUB-2099-001"
        )
        self.assertEqual(result["counts"], self.api["counts"])
        self.assertEqual(json.loads(self.api_path.read_text()), self.api)

    def test_api_wins_conflicts_and_unmatched_rows_never_create_records(self):
        self.api["pubnotes"][0]["finalReferenceCode"] = "ATL-PHYS-PUB-2099-003"
        result = registry.curate(
            self.api,
            {
                "pubnotes": {
                    "PUB-DEMO-2099-01": {
                        "Reference Code": "ATL-PHYS-PUB-2099-001",
                    },
                    "PUB-DEMO-2099-02": {
                        "Reference Code": "ATL-PHYS-PUB-2099-002",
                    },
                }
            },
        )
        self.assertEqual(
            result["pubnotes"][0]["finalReferenceCode"], "ATL-PHYS-PUB-2099-003"
        )
        stats = result["curation"]["supplement_statistics"]["pubnotes"]
        self.assertEqual(stats["conflicting_fields_api_retained"], 1)
        self.assertEqual(stats["supplement_without_api"], 1)
        self.assertEqual(len(result["analyses"]), 1)

    def test_readers_and_repeated_name_parts_are_preserved(self):
        self.assertEqual(registry.person_name(person("Lee", "Lee")), "Lee Lee")
        result = registry.compact(
            {"readers": [person("Reader", isFirstReader=True, isSecondReader=True)]}
        )
        self.assertEqual(result["readers"], ["Reader Example"])
        self.assertEqual(result["firstReaders"], result["secondReaders"])

    def test_retired_html_fields_are_ignored_but_api_values_are_preserved(self):
        self.api["papers"][0]["fullTitle"] = "An API paper title"
        self.api["analyses"][0]["creationDate"] = "2098-12-01"
        result = registry.curate(
            self.api,
            {
                "analyses": {
                    "ANA-DEMO-2099-01": {
                        "Full Title": "An obsolete HTML title",
                        "Internal Note Editors": "",
                    }
                },
                "pubnotes": {
                    "PUB-DEMO-2099-01": {
                        "Reference Code": "",
                        "Creation Date": "2098-11-01",
                    }
                },
            },
        )
        self.assertNotIn("fullTitle", result["analyses"][0])
        self.assertNotIn("creationDate", result["pubnotes"][0])
        self.assertEqual(result["papers"][0]["fullTitle"], "An API paper title")
        self.assertEqual(result["analyses"][0]["creationDate"], "2098-12-01")

    def test_failed_inputs_and_overwriting_source_are_rejected(self):
        before = self.api_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            registry.build_registry(self.api_path, self.csv_dir, self.api_path)
        self.assertEqual(before, self.api_path.read_bytes())
        (self.csv_dir / CSV_REFRESH_MARKER).touch()
        with self.assertRaisesRegex(ValueError, "Incomplete CSV"):
            registry.build_registry(self.api_path, self.csv_dir, self.output)
        self.assertFalse(self.output.exists())

    def test_scope_change_is_rejected_even_with_count_override(self):
        registry.build_registry(self.api_path, self.csv_dir, self.output)
        before = self.output.read_bytes()
        (self.csv_dir / SCOPE_FILENAME).write_text(
            json.dumps(
                {
                    "name": "Synthetic selection",
                    "selection": {
                        "field": "subgroups",
                        "operator": "contains",
                        "values": [901],
                    },
                }
            )
        )
        with self.assertRaisesRegex(ValueError, "scope differs"):
            registry.build_registry(
                self.api_path, self.csv_dir, self.output, allow_count_drop=True
            )
        self.assertEqual(before, self.output.read_bytes())

    def test_count_guard_and_failed_publication_preserve_previous_output(self):
        registry.build_registry(self.api_path, self.csv_dir, self.output)
        previous = json.loads(self.output.read_text())
        for resource in RESOURCES:
            second = copy.deepcopy(previous[resource][0])
            key = (
                "temporaryReferenceCode"
                if resource in {"confnotes", "pubnotes"}
                else "referenceCode"
            )
            second[key] = second[key][:-2] + "02"
            previous[resource].append(second)
            previous["counts"][resource] = 2
        self.output.write_text(json.dumps(previous))
        before = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "20%"):
            registry.build_registry(self.api_path, self.csv_dir, self.output)
        self.assertEqual(before, self.output.read_bytes())
        with (
            patch.object(
                registry, "atomic_write_text", side_effect=OSError("disk full")
            ),
            self.assertRaises(OSError),
        ):
            registry.build_registry(
                self.api_path, self.csv_dir, self.output, allow_count_drop=True
            )
        self.assertEqual(before, self.output.read_bytes())
        registry.build_registry(
            self.api_path, self.csv_dir, self.output, allow_count_drop=True
        )
        self.assertEqual(
            json.loads(self.output.read_text())["counts"], self.api["counts"]
        )


if __name__ == "__main__":
    unittest.main()
