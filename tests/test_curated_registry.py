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
            self.assertEqual(record["gal_analysisContacts"], ["Current Example"])
            self.assertEqual(
                record["gal_contactEditors"], ["Current Example", "Editor Example"]
            )
            phase = record.get("phase0") or record["phase1"]
            self.assertEqual(
                phase["gal_editorialBoard"], ["Chair Example", "Observer Example"]
            )
            self.assertEqual(phase["gal_editorialBoardChairs"], ["Chair Example"])
            self.assertEqual(phase["gal_editorialBoardExOfficio"], ["Observer Example"])
            self.assertEqual(phase["gal_signOffResponsible"], "Official Example")
            self.assertEqual(record["metadata"]["gal_keywords"], ["Keyword", "Other"])
            self.assertEqual(
                record["relatedPublications"],
                self.api[resource][0]["relatedPublications"],
            )
            self.assertNotIn("repositories", record["documentation"])
        self.assertNotIn("cernCcid", json.dumps(result))
        self.assertNotIn("@example.test", json.dumps(result))
        self.assertEqual(before, self.api)

    def test_reserved_namespace_and_removed_keys_are_explicit(self):
        result = registry.curate(self.api, {})
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["gal_curation"]["removed_keys"], registry.REMOVED_KEYS)

        def check_keys(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertNotIn(key, registry.REMOVED_KEYS)
                    check_keys(item)
            elif isinstance(value, list):
                for item in value:
                    check_keys(item)

        for resource in RESOURCES:
            check_keys(result[resource])
        self.api["papers"][0]["metadata"]["gal_future"] = "collision"
        with self.assertRaisesRegex(ValueError, "reserved gal_"):
            registry.curate(self.api, {})

    def test_enrichment_retains_sources_and_removal_is_independent(self):
        source = {
            "keywords": [{"name": "Synthetic keyword"}],
            "analysisTeam": [person("Team")],
            "signOffResponsible": person("Official"),
            "unused": {"dropMe": "value", "keepMe": "value"},
        }
        before = copy.deepcopy(source)
        enriched = registry.compact(source)
        for key, value in source.items():
            self.assertEqual(enriched[key], value)
        self.assertEqual(enriched["gal_keywords"], ["Synthetic keyword"])
        self.assertEqual(enriched["gal_signOffResponsible"], "Official Example")
        pruned = registry.remove_keys(enriched, ["keywords", "dropMe"])
        self.assertNotIn("keywords", pruned)
        self.assertNotIn("dropMe", pruned["unused"])
        self.assertEqual(pruned["gal_keywords"], enriched["gal_keywords"])
        self.assertEqual(pruned["analysisTeam"], source["analysisTeam"])
        self.assertEqual(source, before)
        self.assertIn("keywords", enriched)
        self.assertEqual(registry.remove_keys(enriched, []), enriched)

    def test_string_collections_share_conversion_without_removing_sources(self):
        values = [{"name": " First "}, "Second", {"name": "First"}, {}, None, ""]
        source = {key: copy.deepcopy(values) for key in registry.STRING_LIST_FIELDS}
        before = copy.deepcopy(source)
        result = registry.compact({"nested": source})["nested"]
        for key in registry.STRING_LIST_FIELDS:
            self.assertEqual(result["gal_" + key], ["First", "Second"])
            self.assertEqual(result[key], values)
        self.assertEqual(source, before)
        self.assertEqual(
            registry.string_list([{"label": "Example"}], "label"), ["Example"]
        )
        self.assertEqual(registry.string_list([]), [])
        for invalid in (None, {}, "name"):
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(ValueError, "must be a list"),
            ):
                registry.string_list(invalid)
        with self.assertRaisesRegex(ValueError, "must be strings"):
            registry.string_list([{"name": 42}])

    def test_groups_are_flattened_and_removed_after_enrichment(self):
        groups = {
            "leadingGroup": {"name": "Example group"},
            "leadingSubgroup": {"name": "Example subgroup"},
            "subgroups": [{"name": "Example subgroup"}, {"name": "Other subgroup"}],
            "otherGroups": [{"name": "Other group"}, {"name": "Other group"}],
        }
        before = copy.deepcopy(groups)
        for resource in RESOURCES:
            self.api[resource][0]["groups"] = copy.deepcopy(groups)
        with self.assertNoLogs(registry.logger, level="WARNING"):
            result = registry.curate(self.api, {})
        for resource in RESOURCES:
            record = result[resource][0]
            self.assertNotIn("groups", record)
            self.assertEqual(
                record["gal_groups"],
                {
                    "leadingGroup": "Example group",
                    "leadingSubgroup": "Example subgroup",
                    "subgroups": ["Example subgroup", "Other subgroup"],
                    "otherGroups": ["Other group"],
                },
            )
        self.assertEqual(groups, before)
        self.assertEqual(self.api["analyses"][0]["groups"], before)

    def test_non_singular_leading_assignments_warn_with_record_reference(self):
        self.api["analyses"][0]["groups"] = {
            "leadingGroup": [{"name": "First group"}, {"name": "Second group"}],
            "leadingSubgroup": None,
            "subgroups": [],
            "otherGroups": [],
        }
        with self.assertLogs(registry.logger, level="WARNING") as messages:
            result = registry.curate(self.api, {})
        self.assertEqual(len(messages.output), 1)
        for message in messages.output:
            self.assertIn("ANA-DEMO-2099-01", message)
        groups = result["analyses"][0]["gal_groups"]
        self.assertEqual(groups["leadingGroup"], "First group")
        self.assertIsNone(groups["leadingSubgroup"])
        with self.assertRaisesRegex(ValueError, "Groups must be an object"):
            registry.compact_groups([], reference="DEMO")

    def test_null_leading_assignments_are_preserved_without_warnings(self):
        with self.assertNoLogs(registry.logger, level="WARNING"):
            result = registry.compact_groups(
                {"leadingGroup": None, "leadingSubgroup": None}, reference="DEMO"
            )
        self.assertIsNone(result["leadingGroup"])
        self.assertIsNone(result["leadingSubgroup"])

    def test_meeting_dates_are_extracted_before_source_removal(self):
        meetings = [
            {"date": "2099-01-02T23:30:00-05:00", "title": "Synthetic meeting"},
            {"date": "2099-01-02T12:00:00Z"},
            {"date": "2099-02-03"},
            {"date": None},
            {},
            {"date": ""},
        ]
        for source_key, output_key in registry.MEETING_DATE_FIELDS.items():
            with self.subTest(field=source_key):
                source = {"phase0": {source_key: copy.deepcopy(meetings)}}
                enriched = registry.compact(source)
                self.assertEqual(enriched["phase0"][source_key], meetings)
                result = registry.remove_keys(enriched, registry.REMOVED_KEYS)
                self.assertNotIn(source_key, result["phase0"])
                self.assertEqual(
                    result["phase0"][output_key],
                    ["2099-01-02", "2099-01-02", "2099-02-03"],
                )
                self.assertEqual(source["phase0"][source_key], meetings)
        self.assertEqual(registry.meeting_dates([]), [])
        for invalid in (
            None,
            {},
            ["2099-01-02"],
            [{"date": 42}],
            [{"date": "invalid"}],
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                registry.meeting_dates(invalid)

    def test_repositories_are_dropped_and_statistical_tools_keep_only_names(self):
        for resource in RESOURCES:
            self.api[resource][0]["metadata"]["statisticalTools"] = [
                {"name": "Synthetic tool", "id": 1},
                {"name": "Other tool", "id": 2},
            ]
            self.api[resource][0]["repositories"] = [
                {"url": "https://example.test/code"}
            ]
            self.api[resource][0]["metadata"]["repositories"] = []
        result = registry.curate(self.api, {})
        for resource in RESOURCES:
            record = result[resource][0]
            self.assertNotIn("repositories", record)
            self.assertNotIn("repositories", record["metadata"])
            self.assertNotIn("statisticalTools", record["metadata"])
            self.assertEqual(
                record["metadata"]["gal_statisticalTools"],
                ["Synthetic tool", "Other tool"],
            )

    def test_version_one_output_can_be_rebuilt(self):
        previous = registry.curate(self.api, {})
        previous["schema_version"] = 1
        previous["curation"] = previous.pop("gal_curation")
        _, provenance = registry.read_supplements(self.csv_dir)
        previous["curation"]["html_source"] = provenance
        for resource in RESOURCES:
            for record in previous[resource]:
                for name in ("analysisContacts", "contactEditors"):
                    record[name] = record.pop("gal_" + name)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(previous))
        registry.build_registry(self.api_path, self.csv_dir, self.output)
        rebuilt = json.loads(self.output.read_text())
        self.assertEqual(rebuilt["schema_version"], 2)
        self.assertIn("gal_curation", rebuilt)
        self.assertNotIn("curation", rebuilt)

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
            result["analyses"][0]["gal_internalNoteEditors"],
            ["First Editor", "Second Editor"],
        )
        self.assertEqual(
            result["papers"][0]["gal_figuresUrl"], "https://example.test/figures"
        )
        self.assertNotIn("creationDate", result["pubnotes"][0])
        self.assertEqual(
            result["pubnotes"][0]["gal_finalReferenceCode"], "ATL-PHYS-PUB-2099-001"
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
        stats = result["gal_curation"]["supplement_statistics"]["pubnotes"]
        self.assertEqual(stats["conflicting_fields_api_retained"], 1)
        self.assertEqual(stats["supplement_without_api"], 1)
        self.assertEqual(len(result["analyses"]), 1)

    def test_readers_and_repeated_name_parts_are_preserved(self):
        self.assertEqual(registry.person_name(person("Lee", "Lee")), "Lee Lee")
        result = registry.compact(
            {"readers": [person("Reader", isFirstReader=True, isSecondReader=True)]}
        )
        self.assertEqual(result["gal_readers"], ["Reader Example"])
        self.assertEqual(result["gal_firstReaders"], result["gal_secondReaders"])

    def test_build_embeds_the_selected_citation_store_without_network(self):
        doi = "10.1007/jhep01(2099)001"
        self.api["papers"][0]["publicationPhase"] = {
            "finalJournalPublicationUrls": [{"url": "https://doi.org/" + doi}],
        }
        self.api_path.write_text(json.dumps(self.api))
        cache = self.root / "citations.json"
        cache.write_text(
            json.dumps({doi: {"citation": "Synthetic citation", "source": "manual"}})
        )
        before = cache.read_bytes()
        with patch("requests.get", side_effect=AssertionError("network not allowed")):
            registry.build_registry(
                self.api_path, self.csv_dir, self.output, doi_cache=cache
            )
        result = json.loads(self.output.read_text())
        entry = result["papers"][0]["publicationPhase"]["gal_dois"][0]
        self.assertEqual(entry["citation"], "Synthetic citation")
        self.assertEqual(entry["source"], "manual")
        self.assertTrue(entry["resolved"])
        self.assertEqual(result["gal_curation"]["doi_statistics"]["resolved"], 1)
        self.assertEqual(cache.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            registry.build_registry(self.api_path, self.csv_dir, cache, doi_cache=cache)

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
