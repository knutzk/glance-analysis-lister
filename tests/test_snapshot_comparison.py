# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline comparison semantics and safe report publication."""

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from view_fixtures import analysis, api_fixture, publication, snapshot

from analysis_lister.cli import main
from analysis_lister.registry.comparison import compare_files, compare_snapshots


class SnapshotComparisonTests(unittest.TestCase):
    def setUp(self):
        self.before = snapshot(analysis(1), analysis(2), papers=(publication(1),))

    def test_record_and_dictionary_order_and_container_metadata_are_ignored(self):
        after = copy.deepcopy(self.before)
        after["analyses"].reverse()
        after["papers"][0] = dict(reversed(list(after["papers"][0].items())))
        after["fetched_at"] = "2099-03-01T00:00:00Z"
        after["gal_curation"] = {"built_at": "2099-03-02T00:00:00Z"}
        report = compare_snapshots(self.before, after)
        for changes in report["resources"].values():
            self.assertEqual(changes["counts"]["changed"], 0)
            self.assertEqual(
                changes["counts"]["before"], changes["counts"]["unchanged"]
            )

    def test_added_removed_status_affiliation_doi_and_missing_fields(self):
        after = copy.deepcopy(self.before)
        after["analyses"] = [after["analyses"][0], analysis(3)]
        changed = after["analyses"][0]
        changed["status"] = "Closed"
        changed["gal_groups"]["otherGroups"] = ["OTHER"]
        del changed["shortTitle"]
        changed["optional"] = None
        changed["metadata"]["key/with~punctuation"] = False
        after["papers"][0]["publicationPhase"]["gal_dois"].append(
            {"doi": "10.9999/correction"}
        )
        original = copy.deepcopy(self.before)
        report = compare_snapshots(self.before, after)
        analyses = report["resources"]["analyses"]
        self.assertEqual(
            analyses["counts"],
            {
                "before": 2,
                "after": 2,
                "added": 1,
                "removed": 1,
                "changed": 1,
                "unchanged": 0,
            },
        )
        self.assertEqual(analyses["added"], ["ANA-DEMO-2099-03"])
        self.assertEqual(analyses["removed"], ["ANA-DEMO-2099-02"])
        fields = {field["path"]: field for field in analyses["changed"][0]["fields"]}
        self.assertEqual(fields["/status"]["after"], "Closed")
        self.assertEqual(fields["/gal_groups/otherGroups"]["after"], ["OTHER"])
        self.assertEqual(
            fields["/optional"], {"path": "/optional", "kind": "added", "after": None}
        )
        self.assertNotIn("after", fields["/shortTitle"])
        self.assertIn("/metadata/key~1with~0punctuation", fields)
        self.assertEqual(
            report["resources"]["papers"]["changed"][0]["fields"][0]["path"],
            "/publicationPhase/gal_dois",
        )
        self.assertEqual(self.before, original)

    def test_list_order_and_json_value_types_are_significant(self):
        before = api_fixture()
        before["papers"][0]["flags"] = [True, 1]
        after = copy.deepcopy(before)
        after["papers"][0]["flags"].reverse()
        changes = compare_snapshots(before, after)["resources"]["papers"]["changed"]
        self.assertEqual(
            changes[0]["fields"],
            [
                {
                    "path": "/flags",
                    "kind": "changed",
                    "before": [True, 1],
                    "after": [1, True],
                }
            ],
        )

    def test_mixed_formats_endpoints_and_invalid_snapshots_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "different formats"):
            compare_snapshots(self.before, api_fixture())
        for mutation in ("endpoint", "counts", "duplicates", "schema"):
            after = copy.deepcopy(self.before)
            if mutation == "endpoint":
                after["source"]["base_url"] = "https://other.example.test/api"
            elif mutation == "counts":
                after["counts"]["analyses"] = 99
            elif mutation == "duplicates":
                after["analyses"][1] = copy.deepcopy(after["analyses"][0])
            else:
                after["schema"] = "unknown"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare_snapshots(self.before, after)

    def test_cli_offline_report_contains_values_but_stdout_only_paths(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            before, after, report = (
                root / "before.json",
                root / "after.json",
                root / "nested/report.json",
            )
            before.write_text(json.dumps(self.before))
            updated = copy.deepcopy(self.before)
            updated["analyses"][0]["shortTitle"] = "Private synthetic title μ"
            after.write_text(json.dumps(updated))
            output = io.StringIO()
            with (
                patch("requests.get", side_effect=AssertionError("no network")),
                redirect_stdout(output),
            ):
                main(
                    [
                        "compare-snapshots",
                        str(before),
                        str(after),
                        "--output",
                        str(report),
                        "--details",
                    ]
                )
            self.assertIn("1 changed", output.getvalue())
            self.assertIn("analyses/ANA-DEMO-2099-01", output.getvalue())
            self.assertIn("/shortTitle", output.getvalue())
            self.assertNotIn("Private synthetic title", output.getvalue())
            saved = json.loads(report.read_text())
            self.assertEqual(
                saved["resources"]["analyses"]["changed"][0]["fields"][0]["after"],
                "Private synthetic title μ",
            )
            self.assertEqual(len(saved["inputs"]["before"]["sha256"]), 64)
            for path in (before, after):
                contents = path.read_bytes()
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    compare_files(before, after, output=path)
                self.assertEqual(path.read_bytes(), contents)
            existing = report.read_bytes()
            with (
                patch(
                    "analysis_lister.storage.os.fsync",
                    side_effect=OSError("disk failure"),
                ),
                self.assertRaises(OSError),
            ):
                compare_files(before, after, output=report)
            self.assertEqual(report.read_bytes(), existing)

    def test_validation_failure_preserves_existing_report(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            before, after, output = (
                root / "before.json",
                root / "after.json",
                root / "report.json",
            )
            before.write_text(json.dumps(self.before))
            after.write_text("{}")
            output.write_text("previous report")
            with self.assertRaises(ValueError):
                compare_files(before, after, output=output)
            self.assertEqual(output.read_text(), "previous report")
