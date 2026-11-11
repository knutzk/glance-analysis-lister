# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Generator identity is advisory; data validation and safe publication remain strict."""

import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from view_fixtures import api_fixture, snapshot

from analysis_lister.cli import main
from analysis_lister.downloaders.api import collect_registry, publish_registry
from analysis_lister.downloaders.manifest import make_manifest, validate_manifest
from analysis_lister.provenance import generator_metadata, warn_generator_mismatch
from analysis_lister.registry import CuratedRegistry, validate_registry
from analysis_lister.registry.comparison import compare_snapshots
from analysis_lister.registry.enrichment import curate
from analysis_lister.registry.schema import RESOURCES, validate_api_registry


class GeneratorMetadataTests(unittest.TestCase):
    def test_matching_contents_ignore_commit_and_worktree_identity(self):
        data = {"generator": generator_metadata()}
        data["generator"]["git_commit"] = "a" * 40
        data["generator"]["worktree"] = "/another/checkout"
        with self.assertNoLogs("analysis_lister.provenance", level="WARNING"):
            warn_generator_mismatch(data, label="Snapshot")

    def test_missing_malformed_or_different_metadata_warns_without_leaking_values(self):
        cases = [
            None,
            [],
            "PRIVATE",
            {},
            {"content_sha256": "PRIVATE"},
            {"name": "PRIVATE", "content_sha256": "0" * 64},
            {
                "name": "glance-analysis-lister",
                "content_sha256": "0" * 64,
                "git_commit": "PRIVATE",
            },
        ]
        for metadata in cases:
            with self.subTest(metadata=metadata):
                data = {"generator": metadata}
                with self.assertLogs(
                    "analysis_lister.provenance", level="WARNING"
                ) as logs:
                    warn_generator_mismatch(data, label="Snapshot")
                self.assertEqual(len(logs.output), 1)
                self.assertIn("continuing after validation", logs.output[0])
                self.assertIn("Regenerate", logs.output[0])
                self.assertNotIn("PRIVATE", logs.output[0])

    def test_current_writers_record_metadata_and_omit_format_versions(self):
        api = api_fixture()
        client = SimpleNamespace(
            **{
                resource: SimpleNamespace(
                    search=lambda resource=resource, **kwargs: SimpleNamespace(
                        number_of_results=1,
                        results=[
                            SimpleNamespace(
                                model_dump=lambda **kwargs: api[resource][0]
                            )
                        ],
                    )
                )
                for resource in RESOURCES
            }
        )
        downloaded = collect_registry(client, client_version="synthetic")
        curated = curate(downloaded)
        tasks = [SimpleNamespace(name=resource) for resource in RESOURCES]
        manifest = make_manifest(tasks)
        with self.assertNoLogs("analysis_lister.provenance", level="WARNING"):
            validate_api_registry(downloaded)
            validate_registry(curated)
            validate_manifest(manifest, tasks)
            report = compare_snapshots(curated, curated)
        for data in (downloaded, curated, manifest, report):
            self.assertNotIn("schema_version", data)
            self.assertEqual(data["generator"], generator_metadata())
            self.assertEqual(list(data)[:2], ["schema", "generator"])

    def test_legacy_api_and_manifest_version_fields_are_ignored(self):
        api = api_fixture()
        api.pop("generator")
        api["schema_version"] = 999
        before = copy.deepcopy(api)
        with self.assertLogs("analysis_lister.provenance", level="WARNING"):
            curated = curate(api)
        self.assertEqual(api, before)
        self.assertNotIn("schema_version", curated)
        self.assertEqual(curated["generator"], generator_metadata())
        manifest = make_manifest([])
        manifest.pop("generator")
        manifest["schema_version"] = 999
        with self.assertLogs("analysis_lister.provenance", level="WARNING"):
            self.assertEqual(validate_manifest(manifest, []), manifest)

    def test_reader_warning_does_not_modify_or_reject_valid_records(self):
        data = snapshot()
        data["generator"]["content_sha256"] = "0" * 64
        before = copy.deepcopy(data)
        with self.assertLogs("analysis_lister.provenance", level="WARNING"):
            reader = CuratedRegistry(data)
        self.assertEqual(data, before)
        self.assertEqual(reader.metadata["generator"], before["generator"])
        self.assertEqual(reader.records("analyses"), tuple(before["analyses"]))
        data["counts"]["analyses"] = -1
        with self.assertRaises(ValueError):
            CuratedRegistry(data)

    def test_warning_does_not_bypass_count_drop_or_endpoint_checks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "api.json"
            original = api_fixture()
            original["generator"]["content_sha256"] = "0" * 64
            for resource in RESOURCES:
                second = copy.deepcopy(original[resource][0])
                key = (
                    "referenceCode"
                    if resource in ("analyses", "papers")
                    else "temporaryReferenceCode"
                )
                second[key] += "-SECOND"
                original[resource].append(second)
                original["counts"][resource] = 2
            path.write_text(json.dumps(original))
            raw = path.read_bytes()
            candidate = api_fixture()
            with (
                self.assertLogs("analysis_lister.provenance", level="WARNING"),
                self.assertRaisesRegex(ValueError, "count dropped"),
            ):
                publish_registry(candidate, path)
            self.assertEqual(path.read_bytes(), raw)
            candidate["source"]["base_url"] = "https://other.example.test/api"
            with (
                self.assertLogs("analysis_lister.provenance", level="WARNING"),
                self.assertRaisesRegex(ValueError, "endpoint differs"),
            ):
                publish_registry(candidate, path, allow_count_drop=True)
            self.assertEqual(path.read_bytes(), raw)

    def test_cli_warns_on_stderr_even_when_quiet_and_continues_offline(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            api, curated, pages = (
                root / "api.json",
                root / "curated.json",
                root / "pages",
            )
            data = api_fixture()
            data["generator"]["content_sha256"] = "0" * 64
            api.write_text(json.dumps(data))
            for flags in ([], ["--quiet"]):
                with (
                    redirect_stdout(io.StringIO()) as stdout,
                    redirect_stderr(io.StringIO()) as stderr,
                    patch(
                        "socket.socket.connect", side_effect=AssertionError("network")
                    ),
                ):
                    main(
                        [
                            "build-registry",
                            "--api-snapshot",
                            str(api),
                            "--output",
                            str(curated),
                            *flags,
                        ]
                    )
                self.assertIn("different package code", stderr.getvalue())
                self.assertNotIn("different package code", stdout.getvalue())
                self.assertTrue(curated.exists())
            generated = json.loads(curated.read_text())
            generated.pop("generator")
            curated.write_text(json.dumps(generated))
            with (
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()) as stderr,
            ):
                main(
                    [
                        "render-group",
                        "--group",
                        "DEMO",
                        "--snapshot",
                        str(curated),
                        "--output-dir",
                        str(pages),
                        "--quiet",
                    ]
                )
            self.assertIn("generator metadata", stderr.getvalue())
            report = json.loads((pages / "view-report.json").read_text())
            self.assertNotIn("schema_version", report)
            self.assertEqual(report["generator"], generator_metadata())

    def test_citation_store_has_no_generator_requirement(self):
        from analysis_lister.citations.store import load_store, save_store

        with TemporaryDirectory() as directory:
            path = Path(directory) / "citations.json"
            entries = {
                "10.9999/example": {"citation": "Invented citation", "source": "manual"}
            }
            with self.assertNoLogs("analysis_lister.provenance", level="WARNING"):
                save_store(path, entries)
                self.assertEqual(load_store(path), entries)
