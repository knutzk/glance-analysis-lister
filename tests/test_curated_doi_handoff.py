# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Resolve DOI inputs produced by the actual offline registry builder."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from view_fixtures import api_fixture

from grove import cli
from grove.citations.resolver import snapshot_dois
from grove.citations.store import load_store, save_store
from grove.registry.builder import build_registry

ORIGINAL = "10.1007/jhep01(2099)001"
CORRECTION = "10.1007/jhep02(2099)002"
UNRESOLVED = "10.1007/jhep03(2099)003"


class CuratedDoiHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api = self.root / "api.json"
        self.curated = self.root / "curated.json"
        self.store = self.root / "citations.json"
        self.manual = {
            ORIGINAL: {
                "citation": "Invented original citation",
                "source": "manual",
                "material": "publication",
                "source_url": "https://example.test/original",
                "resolved_at": "2099-01-01T00:00:00+00:00",
            },
            CORRECTION: {
                "citation": "Invented correction citation",
                "source": "manual",
                "material": "erratum",
                "source_url": "https://example.test/correction",
                "resolved_at": "2099-02-01T00:00:00+00:00",
            },
        }
        save_store(self.store, self.manual)
        api = api_fixture()
        api["papers"][0]["publicationPhase"] = {
            "finalJournalPublicationUrls": [
                {"url": "https://doi.org/" + doi}
                for doi in (UNRESOLVED, CORRECTION, ORIGINAL)
            ]
        }
        self.api.write_text(json.dumps(api))
        self.enterContext(
            patch(
                "requests.sessions.Session.request",
                side_effect=AssertionError("No network allowed"),
            )
        )
        build_registry(self.api, self.curated, doi_cache=self.store)

    def test_actual_builder_output_supplies_the_same_dois_as_api_input(self):
        phase = json.loads(self.curated.read_text())["papers"][0]["publicationPhase"]
        self.assertNotIn("finalJournalPublicationUrls", phase)
        self.assertEqual(
            {entry["doi"] for entry in phase["gal_dois"]},
            {ORIGINAL, CORRECTION, UNRESOLVED},
        )
        before = self.curated.read_bytes()
        self.assertEqual(snapshot_dois(self.api), {ORIGINAL, CORRECTION, UNRESOLVED})
        self.assertEqual(snapshot_dois(self.curated), snapshot_dois(self.api))
        self.assertEqual(self.curated.read_bytes(), before)

    def test_cli_resolves_built_snapshot_and_preserves_manual_correction_metadata(self):
        before = self.curated.read_bytes()
        api_before = self.api.read_bytes()
        with (
            patch(
                "grove.citations.resolver.InspireClient",
                side_effect=AssertionError("Offline inference must not query INSPIRE"),
            ),
            redirect_stdout(io.StringIO()),
        ):
            cli.main(
                [
                    "resolve-dois",
                    "--snapshot",
                    str(self.curated),
                    "--doi-cache",
                    str(self.store),
                    "--method",
                    "infer",
                    "--refresh-existing",
                ]
            )
        entries = load_store(self.store)
        self.assertEqual(set(entries), {ORIGINAL, CORRECTION, UNRESOLVED})
        for doi, metadata in self.manual.items():
            self.assertEqual(entries[doi], metadata)
        self.assertEqual(entries[UNRESOLVED]["citation"], "JHEP 03 (2099) 003")
        self.assertEqual(entries[UNRESOLVED]["source"], "doi-pattern:jhep")
        self.assertEqual(self.curated.read_bytes(), before)
        self.assertEqual(self.api.read_bytes(), api_before)

        build_registry(self.api, self.curated, doi_cache=self.store)
        phase = json.loads(self.curated.read_text())["papers"][0]["publicationPhase"]
        self.assertEqual(
            [(entry["doi"], entry["citation"]) for entry in phase["gal_dois"]],
            [
                (doi, entries[doi]["citation"])
                for doi in (ORIGINAL, CORRECTION, UNRESOLVED)
            ],
        )

    def test_curated_entries_normalize_deduplicate_and_skip_bad_dois_without_guessing(
        self,
    ):
        data = json.loads(self.curated.read_text())
        data["papers"][0]["publicationPhase"]["gal_dois"] = [
            {
                "doi": ORIGINAL.upper(),
                "url": "https://doi.org/" + UNRESOLVED,
                "citation": "DOI: " + UNRESOLVED,
            },
            {"doi": "https://doi.org/" + ORIGINAL},
            {"doi": CORRECTION},
            {"doi": "invented-private-value"},
            {"doi": None},
            {},
            "not an entry",
            {"doi": 42},
            {"url": "https://doi.org/" + UNRESOLVED},
        ]
        self.curated.write_text(json.dumps(data))
        before = self.curated.read_bytes()
        with self.assertLogs("grove.citations.resolver", level="WARNING") as logs:
            self.assertEqual(snapshot_dois(self.curated), {ORIGINAL, CORRECTION})
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Skipped 6 malformed DOI values", logs.output[0])
        self.assertNotIn("invented-private-value", logs.output[0])
        self.assertEqual(self.curated.read_bytes(), before)

    def test_missing_phase_or_doi_collection_has_no_dois(self):
        data = json.loads(self.curated.read_text())
        for fields in (
            {},
            {"publicationPhase": None},
            {"publicationPhase": {}},
            {"publicationPhase": {"gal_dois": []}},
            {
                "publicationPhase": {
                    "finalJournalPublicationUrls": [
                        {"url": "https://doi.org/" + ORIGINAL}
                    ]
                }
            },
            {
                "publicationPhase": {
                    "gal_dois": [],
                    "finalJournalPublicationUrls": [
                        {"url": "https://doi.org/" + ORIGINAL}
                    ],
                }
            },
        ):
            with self.subTest(fields=fields):
                data["papers"] = [{"referenceCode": "DEMO-2099-01", **fields}]
                self.curated.write_text(json.dumps(data))
                with self.assertNoLogs("grove", level="WARNING"):
                    self.assertEqual(snapshot_dois(self.curated), set())

    def test_invalid_curated_containers_are_rejected(self):
        data = json.loads(self.curated.read_text())
        for phase in (
            [],
            "invented-private-value",
            False,
            0,
            *({"gal_dois": value} for value in (None, {}, "", False, 0)),
        ):
            with self.subTest(phase=phase):
                data["papers"][0]["publicationPhase"] = phase
                self.curated.write_text(json.dumps(data))
                with self.assertRaises(ValueError) as raised:
                    snapshot_dois(self.curated)
                self.assertNotIn("invented-private-value", str(raised.exception))

    def test_cli_rejects_invalid_curated_collection_without_touching_citations(self):
        data = json.loads(self.curated.read_text())
        data["papers"][0]["publicationPhase"]["gal_dois"] = "invented-private-value"
        self.curated.write_text(json.dumps(data))
        store_before, snapshot_before = (
            self.store.read_bytes(),
            self.curated.read_bytes(),
        )
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            cli.main(
                [
                    "resolve-dois",
                    "--snapshot",
                    str(self.curated),
                    "--doi-cache",
                    str(self.store),
                ]
            )
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("rebuild from a saved API snapshot", stderr.getvalue())
        self.assertNotIn("invented-private-value", stderr.getvalue())
        self.assertEqual(self.store.read_bytes(), store_before)
        self.assertEqual(self.curated.read_bytes(), snapshot_before)
