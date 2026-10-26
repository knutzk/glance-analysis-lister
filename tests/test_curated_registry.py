# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Synthetic API-to-curated mapping and offline publication regressions."""

import copy
import json
import subprocess
import sys
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from view_fixtures import api_fixture, person

from analysis_lister import cli
from analysis_lister.download import RESOURCES
from analysis_lister.registry import builder, enrichment as registry
from analysis_lister.registry.fields import RECORD_FIELDS, select_fields
from analysis_lister.registry.schema import validate_registry


class CuratedTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api_path = self.root / "api.json"
        self.output = self.root / "nested" / "curated.json"
        self.api = api_fixture()
        self.api_path.write_text(json.dumps(self.api))

    def test_default_build_reads_and_writes_in_callers_working_directory(self):
        with TemporaryDirectory() as workspace, chdir(workspace):
            Path("glance_api_registry.json").write_bytes(self.api_path.read_bytes())
            cli.main(["build-registry"])
            result = json.loads(Path("glance_curated_registry.json").read_text())
            validate_registry(result)
            self.assertFalse(Path("json").exists())
            self.assertFalse(Path("csv").exists())

    def test_people_keywords_and_other_data_are_consolidated_without_mutating_input(
        self,
    ):
        before = copy.deepcopy(self.api)
        result = registry.curate(self.api)
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
            if resource != "analyses":
                self.assertEqual(
                    phase["gal_editorialBoardExOfficio"], ["Observer Example"]
                )
            self.assertNotIn("gal_signOffResponsible", phase)
            self.assertEqual(record["metadata"]["gal_keywords"], ["Keyword", "Other"])
            if resource == "analyses":
                self.assertEqual(
                    record["relatedPublications"],
                    self.api[resource][0]["relatedPublications"],
                )
            else:
                self.assertNotIn("relatedPublications", record)
            self.assertNotIn("repositories", record["documentation"])
        self.assertNotIn("cernCcid", json.dumps(result))
        self.assertNotIn("@example.test", json.dumps(result))
        self.assertEqual(before, self.api)

    def test_reserved_namespace_collisions_are_rejected(self):
        self.api["papers"][0]["metadata"]["gal_future"] = "collision"
        with self.assertRaisesRegex(ValueError, "reserved gal_"):
            registry.curate(self.api)

    def test_enrichment_retains_sources_without_mutating_input(self):
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
        self.assertEqual(source, before)

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
            result = registry.curate(self.api)
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
            result = registry.curate(self.api)
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
                result = select_fields(enriched, RECORD_FIELDS["analyses"])
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
        result = registry.curate(self.api)
        for resource in RESOURCES:
            record = result[resource][0]
            self.assertNotIn("repositories", record)
            self.assertNotIn("repositories", record["metadata"])
            self.assertNotIn("statisticalTools", record["metadata"])
            self.assertEqual(
                record["metadata"]["gal_statisticalTools"],
                ["Synthetic tool", "Other tool"],
            )

    def test_old_schema_output_is_rejected_without_overwriting_it(self):
        previous = registry.curate(self.api)
        previous["schema_version"] = 1
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(previous))
        before = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "supported curated registry"):
            builder.build_registry(self.api_path, self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_new_workflow_runs_with_legacy_and_authentication_imports_blocked(self):
        code = """
import importlib.abc
import sys
class BlockLegacyAndAuthentication(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".")
               for name in ("analysis_lister.glance", "stare", "selenium")):
            raise AssertionError("Forbidden dependency: " + fullname)
sys.meta_path.insert(0, BlockLegacyAndAuthentication())
from analysis_lister import download
from analysis_lister.cli import main
from analysis_lister.registry import CuratedRegistry
main(["build-registry", "--api-snapshot", sys.argv[1],
      "--output", sys.argv[2]])
registry = CuratedRegistry.from_json(sys.argv[2])
assert registry.get("analyses", "ANA-DEMO-2099-01") is not None
assert not any(name.startswith("analysis_lister.glance") for name in sys.modules)
"""
        subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                str(self.api_path),
                str(self.output),
            ],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_complete_offline_cli_build_needs_no_supplements(self):
        self.api["papers"][0]["status"] = "Publication Phase Finished"
        self.api["pubnotes"][0]["phase1"]["publicWebPageUrlForFiguresAndTables"] = (
            "https://example.test/ATL-PHYS-PUB-2099-001/"
        )
        self.api_path.write_text(json.dumps(self.api))
        with patch(
            "stare.auth.TokenManager", side_effect=AssertionError("No authentication")
        ):
            cli.main(
                [
                    "build-registry",
                    "--api-snapshot",
                    str(self.api_path),
                    "--output",
                    str(self.output),
                ]
            )
        result = json.loads(self.output.read_text())
        validate_registry(result)
        self.assertNotIn("fullTitle", result["analyses"][0])
        self.assertNotIn("gal_internalNoteEditors", result["analyses"][0])
        self.assertNotIn("html_source", result["gal_curation"])
        self.assertEqual(
            result["papers"][0]["gal_figuresUrl"],
            "https://atlas.web.cern.ch/Atlas/GROUPS/PHYSICS/PAPERS/DEMO-2099-01/",
        )
        self.assertNotIn("creationDate", result["pubnotes"][0])
        self.assertEqual(
            result["pubnotes"][0]["gal_finalReferenceCode"], "ATL-PHYS-PUB-2099-001"
        )
        self.assertEqual(result["counts"], self.api["counts"])
        self.assertEqual(json.loads(self.api_path.read_text()), self.api)

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
            builder.build_registry(self.api_path, self.output, doi_cache=cache)
        result = json.loads(self.output.read_text())
        entry = result["papers"][0]["publicationPhase"]["gal_dois"][0]
        self.assertEqual(entry["citation"], "Synthetic citation")
        self.assertEqual(set(entry), {"doi", "url", "citation"})
        self.assertEqual(result["gal_curation"]["doi_statistics"]["resolved"], 1)
        self.assertEqual(cache.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            builder.build_registry(self.api_path, cache, doi_cache=cache)

    def test_unused_api_title_and_creation_values_are_dropped(self):
        self.api["papers"][0]["fullTitle"] = "An API paper title"
        self.api["analyses"][0]["creationDate"] = "2098-12-01"
        result = registry.curate(self.api)
        self.assertNotIn("fullTitle", result["analyses"][0])
        self.assertNotIn("creationDate", result["pubnotes"][0])
        self.assertNotIn("fullTitle", result["papers"][0])
        self.assertNotIn("creationDate", result["analyses"][0])

    def test_failed_inputs_and_overwriting_source_are_rejected(self):
        before = self.api_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            builder.build_registry(self.api_path, self.api_path)
        self.assertEqual(before, self.api_path.read_bytes())
        self.api["counts"]["papers"] = 99
        self.api_path.write_text(json.dumps(self.api))
        with self.assertRaises(ValueError):
            builder.build_registry(self.api_path, self.output)
        self.assertFalse(self.output.exists())

    def test_invalid_api_is_rejected_even_with_count_override(self):
        builder.build_registry(self.api_path, self.output)
        before = self.output.read_bytes()
        self.api["source"]["selection"] = "filtered"
        self.api_path.write_text(json.dumps(self.api))
        with self.assertRaises(ValueError):
            builder.build_registry(self.api_path, self.output, allow_count_drop=True)
        self.assertEqual(before, self.output.read_bytes())

    def test_count_guard_and_failed_publication_preserve_previous_output(self):
        builder.build_registry(self.api_path, self.output)
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
            builder.build_registry(self.api_path, self.output)
        self.assertEqual(before, self.output.read_bytes())
        with (
            patch.object(
                builder, "atomic_write_text", side_effect=OSError("disk full")
            ),
            self.assertRaises(OSError),
        ):
            builder.build_registry(self.api_path, self.output, allow_count_drop=True)
        self.assertEqual(before, self.output.read_bytes())
        builder.build_registry(self.api_path, self.output, allow_count_drop=True)
        self.assertEqual(
            json.loads(self.output.read_text())["counts"], self.api["counts"]
        )


if __name__ == "__main__":
    unittest.main()
