# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Stored-data validation: historical sparse inputs, independent of curation and views."""

import copy
import json
import unittest
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from grove.registry import CuratedRegistry
from grove.registry.fields import RECORD_FIELDS
from grove.registry.schema import RESOURCES, validate_registry

FIXTURES = Path(__file__).parent / "fixtures/curated"
PAPER_TIMESTAMP_FIELDS = (
    "arXivSubmissionDate",
    "firstRefereeReportDate",
    "firstProofDate",
    "publishedOnlineDate",
)


def baseline():
    return json.loads((FIXTURES / "v2-baseline.json").read_text())


def schema():
    return json.loads(
        files("grove.registry").joinpath("schemas/curated.schema.json").read_text()
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

    def test_historical_sparse_fixtures_preserve_values_without_defaults(self):
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

    def test_paper_timestamps_preserve_source_precision_and_historical_values(self):
        validator = Draft202012Validator(schema(), format_checker=FormatChecker())
        for value in (
            "2099-03-05T14:30",
            "2000-02-29T00:00",
            "2400-02-29T23:59",
            "2096-02-29T12:30",
            "0001-01-01T00:00",
            "9999-12-31T23:59",
            "2099-03-05",
            "2099-03-05T23:30:00-05:00",
            None,
            "",
        ):
            with self.subTest(value=value):
                data = baseline()
                phase = data["papers"][0]["publicationPhase"]
                phase.update(dict.fromkeys(PAPER_TIMESTAMP_FIELDS, value))
                before = copy.deepcopy(data)
                validator.validate(data)
                loaded = CuratedRegistry(data)
                self.assertEqual(loaded.records("papers")[0], before["papers"][0])
                self.assertEqual(data, before)

    def test_invalid_local_paper_timestamps_fail_in_standalone_and_package_validation(
        self,
    ):
        validator = Draft202012Validator(schema(), format_checker=FormatChecker())
        for field in PAPER_TIMESTAMP_FIELDS:
            for value in (
                "2099-02-29T12:30",
                "2100-02-29T12:30",
                "1900-02-29T12:30",
                "2000-02-30T12:30",
                "2099-04-31T12:30",
                "2099-13-01T12:30",
                "2099-01-00T12:30",
                "0000-01-01T12:30",
                "2099-01-01T24:00",
                "2099-01-01T12:60",
                "2099-1-01T12:30",
                "2099-01-01 12:30",
                "2099-01-01T12:30:00",
                "2099-01-01T12:30.5",
                "2099-01-01T12:30\n",
                "2099-01-01T12:30junk",
            ):
                with self.subTest(field=field, value=value):
                    data = baseline()
                    data["papers"][0]["publicationPhase"][field] = value
                    self.assertFalse(validator.is_valid(data))
                    with self.assertRaisesRegex(ValueError, field):
                        validate_registry(data)

    def test_local_minute_timestamps_are_limited_to_four_paper_fields(self):
        for path in (
            ("fetched_at",),
            ("papers", 0, "publicationPhase", "startDate"),
            ("papers", 0, "publicationPhase", "journalAcceptanceDate"),
            ("analyses", 0, "phase0", "startDate"),
            ("confnotes", 0, "phase1", "releaseDate"),
            ("pubnotes", 0, "phase1", "releaseDate"),
        ):
            with self.subTest(path=path):
                data = baseline()
                data["pubnotes"][0]["phase1"] = {}
                parent = data
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = "2099-03-05T14:30"
                with self.assertRaisesRegex(ValueError, path[-1]):
                    validate_registry(data)

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

    def test_legacy_version_fields_do_not_gate_structurally_valid_data(self):
        for version in (1, 3, "2", 2.0, True, None):
            with self.subTest(version=version):
                data = baseline()
                data["schema_version"] = version
                with self.assertLogs("grove.provenance", level="WARNING") as logs:
                    validate_registry(data)
                self.assertIn("generator metadata", logs.output[0])

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
