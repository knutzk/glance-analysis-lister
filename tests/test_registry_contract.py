# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Stable storage contract: fixtures are independent of curation and views."""

import copy
import json
import unittest
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from analysis_lister.registry import CuratedRegistry
from analysis_lister.registry.fields import RECORD_FIELDS
from analysis_lister.registry.schema import RESOURCES, validate_registry

FIXTURES = Path(__file__).parent / "fixtures/curated"


def baseline():
    return json.loads((FIXTURES / "v2-baseline.json").read_text())


def schema():
    return json.loads(
        files("analysis_lister.registry")
        .joinpath("schemas/curated-v2.schema.json")
        .read_text()
    )


class RegistryContractTests(unittest.TestCase):
    def test_schema_is_valid_and_all_references_are_local(self):
        contract = schema()
        Draft202012Validator.check_schema(contract)

        def check(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    self.assertTrue(value["$ref"].startswith("#/$defs/"))
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)

        check(contract)

    def test_frozen_fixtures_load_without_migration_or_defaults(self):
        validator = Draft202012Validator(schema(), format_checker=FormatChecker())
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=path.name):
                data = json.loads(path.read_text())
                before = copy.deepcopy(data)
                validator.validate(data)
                loaded = CuratedRegistry(data)
                self.assertEqual(data, before)
                for resource in RESOURCES:
                    self.assertEqual(list(loaded.records(resource)), data[resource])
        self.assertNotIn(
            "finalSubmissionJournal",
            CuratedRegistry(baseline()).records("papers")[0]["publicationPhase"],
        )

    def test_unknown_additions_and_new_source_codes_are_preserved(self):
        data = baseline()
        data["futureMetadata"] = {"anything": [1, None]}
        paper = data["papers"][0]
        paper["futureField"] = False
        paper["status"] = "An unseen source state"
        paper["publicationPhase"].update(
            futureMilestone={"anything": True}, finalSubmissionJournal="NEW_CODE"
        )
        reader = CuratedRegistry(data)
        self.assertEqual(reader.records("papers")[0], paper)
        self.assertEqual(reader.metadata["futureMetadata"], data["futureMetadata"])

    def test_empty_collections_and_missing_optional_fields_are_valid(self):
        data = baseline()
        for key in ("fetched_at",):
            del data[key]
        for resource in RESOURCES:
            data[resource] = []
            data["counts"][resource] = 0
        validate_registry(data)

    def test_known_nested_fields_fail_with_paths_without_values(self):
        cases = [
            (("papers", 0, "publicationPhase"), []),
            (
                ("papers", 0, "publicationPhase", "journalAcceptanceDate"),
                "PRIVATE_BAD_DATE",
            ),
            (("papers", 0, "publicationPhase", "journalAcceptanceDate"), "2099-02-30"),
            (
                ("papers", 0, "publicationPhase", "journalAcceptanceDate"),
                "2099-01-14T25:00:00Z",
            ),
            (("papers", 0, "relatedAnalysis"), "PRIVATE_BAD_LINK"),
            (("papers", 0, "relatedAnalysis", "referenceCode"), 123),
            (("analyses", 0, "gal_analysisContacts"), [123]),
            (("analyses", 0, "phase0", "gal_editorialBoard"), [None]),
            (("analyses", 0, "phase0", "gal_approvalMeetingDates"), ["2099-02-30"]),
            (("pubnotes", 0, "metadata", "collisions"), {}),
            (("fetched_at",), "PRIVATE_BAD_TIMESTAMP"),
            (("counts", "analyses"), True),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                data = baseline()
                parent = data
                for part in path[:-1]:
                    parent = parent[part]
                parent[path[-1]] = value
                with self.assertRaises(ValueError) as caught:
                    validate_registry(data)
                message = str(caught.exception)
                self.assertIn(str(path[-1]), message)
                self.assertNotIn("PRIVATE_", message)

    def test_missing_required_fields_and_source_people_are_rejected(self):
        data = baseline()
        del data["papers"][0]["gal_contactEditors"]
        with self.assertRaisesRegex(
            ValueError, "missing required field.*gal_contactEditors"
        ):
            validate_registry(data)
        data = baseline()
        data["papers"][0]["analysisTeam"] = []
        with self.assertRaises(ValueError):
            validate_registry(data)

    def test_integrity_checks_are_separate_from_structural_validation(self):
        data = baseline()
        data["papers"].append(copy.deepcopy(data["papers"][0]))
        data["counts"]["papers"] = 2
        Draft202012Validator(schema()).validate(data)
        with self.assertRaisesRegex(ValueError, "inconsistent counts or identifiers"):
            validate_registry(data)
        data = baseline()
        data["counts"]["papers"] = 2
        with self.assertRaisesRegex(ValueError, "inconsistent counts or identifiers"):
            validate_registry(data)

    def test_unresolved_links_are_valid_without_guessing_or_network(self):
        data = baseline()
        link = data["papers"][0]["relatedAnalysis"]
        link["referenceCode"] = "ANA-FIXTURE-2099-MISSING"
        reader = CuratedRegistry(data)
        self.assertIsNone(reader.resolve_link(link))
        # New type codes can be stored, but this reader cannot resolve them.
        link["type"] = "Future resource"
        reader = CuratedRegistry(data)
        with self.assertRaisesRegex(ValueError, "known type"):
            reader.resolve_link(link)

    def test_versions_are_not_silently_coerced(self):
        for version in (1, 3, "2", 2.0, True, None):
            with self.subTest(version=version):
                data = baseline()
                data["schema_version"] = version
                with self.assertRaisesRegex(ValueError, "expected schema_version 2"):
                    validate_registry(data)

    def test_projection_fields_are_covered_by_the_contract(self):
        contract = schema()

        def properties(node):
            if "$ref" in node:
                node = contract["$defs"][node["$ref"].rsplit("/", 1)[-1]]
            if "items" in node:
                return properties(node["items"])
            result = dict(node.get("properties", {}))
            for branch in node.get("allOf", []) + node.get("anyOf", []):
                result.update(properties(branch))
            return result

        def covered(selection, node, path):
            fields = properties(node)
            self.assertEqual(set(selection), set(fields) - {"analysisTeam"}, path)
            for name, nested in selection.items():
                if nested is not None:
                    covered(nested, fields[name], path + "." + name)

        for resource, selection in RECORD_FIELDS.items():
            covered(selection, contract["properties"][resource], resource)


if __name__ == "__main__":
    unittest.main()
