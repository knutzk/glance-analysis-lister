# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline citation migration, incremental resolution and public API boundaries."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests

from analysis_lister import cli
from analysis_lister.citation_store import (
    Citations,
    cached_citations,
    load_store,
    normalize_doi,
    save_store,
)
from analysis_lister.doi_resolver import (
    InspireClient,
    format_citations,
    format_journal_name,
    infer_citation,
    inspire_citation,
    resolve_dois,
    snapshot_dois,
)
from analysis_lister.glance.paper import Paper
from analysis_lister.lookup_validation import validate_lookups

DOI = "10.9999/demo"
JHEP = "10.1007/JHEP07(2099)999"


def record(citation="Demo J. 12 (2099) 123", **changes):
    return {"citation": citation, "source": "manual"} | changes


def payload(doi=DOI):
    return {
        "metadata": {
            "control_number": 123456,
            "dois": [{"value": doi}],
            "publication_info": [
                {
                    "journal_title": "Demo J.",
                    "journal_volume": "12",
                    "year": 2099,
                    "artid": "123",
                }
            ],
        }
    }


def response(status=200, data=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = data if data is not None else payload()
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(
            "synthetic HTTP failure"
        )
    return result


class CitationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "nested/citations.json"

    def test_curated_defaults_are_rich_and_preserve_corrections(self):
        validate_lookups()
        for value in Citations.values():
            self.assertIn("source", value)
            self.assertNotIn("locked", value)
            self.assertTrue(value["citation"])
        self.assertEqual(
            Citations["10.1140/epjc/s10052-020-08541-3"]["citation"],
            "Erratum: Eur. Phys. J. C 80 (2020) 1092",
        )

    def test_store_does_not_merge_another_dictionary(self):
        save_store(self.path, {DOI: record("User correction", source="inspire")})
        loaded = load_store(self.path)
        self.assertEqual(loaded[DOI]["citation"], "User correction")
        self.assertEqual(loaded[DOI]["source"], "inspire")
        self.assertEqual(set(loaded), {DOI})
        self.assertEqual(load_store(self.root / "missing.json"), {})

    def test_one_line_per_doi_and_redundant_legacy_fields_are_removed(self):
        values = {
            DOI: record('Citation with "quotes" and Unicode γ', locked=False),
            "10.9999/other": record(source="inspire", locked=True, material="unknown"),
        }
        save_store(self.path, values)
        text = self.path.read_text()
        self.assertEqual(len(text.splitlines()), 4)
        self.assertNotIn('"locked"', text)
        self.assertNotIn('"material"', text)
        self.assertEqual(load_store(self.path)[DOI]["source"], "manual")
        self.assertEqual(load_store(self.path)["10.9999/other"]["source"], "inspire")

    def test_duplicate_and_invalid_json_records_are_rejected(self):
        self.path.parent.mkdir()
        for text in (
            "[]",
            f'{{"{DOI}": {{}}, "{DOI}": {{}}}}',
            json.dumps({DOI: record(), DOI.upper(): record()}),
            json.dumps({DOI: record(locked="true")}),
            '{"10.9999/demo": {"citation": "Demo", "source": "manual", "source": "inspire"}}',
        ):
            self.path.write_text(text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                load_store(self.path)

    def test_cached_citations_restore_after_failure_and_feed_json_loading_offline(self):
        save_store(self.path, {DOI: record("Cached citation")})
        original = Citations.copy()
        with (
            self.assertRaisesRegex(RuntimeError, "synthetic"),
            cached_citations(self.path),
        ):
            self.assertEqual(Citations[DOI]["citation"], "Cached citation")
            raise RuntimeError("synthetic")
        self.assertEqual(Citations, original)
        from attrs import fields

        data = {f.name: "" for f in fields(Paper) if f.init}
        data.update(
            ref_code="DEMO-2099-01",
            status=" Phase 0 is  Finished ",
            status_paper=" Publication Phase is  Active ",
            date_publication="2099-01-01",
            doi_urls=[f"https://doi.org/{DOI}"],
            keywords=[],
            subgroups=[],
            supporting_docs=[],
        )
        with (
            cached_citations(self.path),
            patch.object(
                requests.Session, "get", side_effect=AssertionError("network")
            ),
        ):
            paper = Paper.from_json(data)
        self.assertEqual(paper.journal_ref, "Cached citation")


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "citations.json"

    def test_journal_aliases_match_manual_typography_and_preserve_unknown_names(self):
        for raw, expected in (
            ("Phys.Rev.D", "Phys. Rev. D"),
            (" Phys. Rev. Lett. ", "Phys. Rev. Lett."),
            ("Phys.Lett.B", "Phys. Lett. B"),
            ("Eur.Phys.J.C", "Eur. Phys. J. C"),
            ("Phys.Rept.", "Phys. Rep."),
            ("Rept.Prog.Phys.", "Rep. Prog. Phys."),
            ("Comput.Softw.Big Sci.", "Comput. Softw. Big Sci."),
            ("New J.Phys.", "New J. Phys."),
            ("JHEP", "JHEP"),
            ("JINST", "JINST"),
            ("Unknown.Journal", "Unknown.Journal"),
        ):
            with self.subTest(journal=raw):
                self.assertEqual(format_journal_name(raw), expected)

    def test_inspire_formats_journal_name_when_resolving(self):
        data = payload()
        data["metadata"]["publication_info"][0]["journal_title"] = "Phys.Rev.D"
        self.assertEqual(
            inspire_citation(DOI, data)["citation"], "Phys. Rev. D 12 (2099) 123"
        )

    def test_offline_formatting_preserves_manual_entries_provenance_and_corrections(
        self,
    ):
        automated = record(
            "Erratum: Phys.Rev.D 12 (2099) 00123",
            source="inspire",
            material="erratum",
            resolved_at="2099-01-01T00:00:00+00:00",
        )
        manual = record("Phys.Rev.D 13 (2099) 00456")
        save_store(self.path, {DOI: automated, "10.9999/manual": manual})
        with patch.object(
            requests.Session, "get", side_effect=AssertionError("network")
        ):
            self.assertEqual(format_citations(self.path), 1)
            before = self.path.read_bytes()
            self.assertEqual(format_citations(self.path), 0)
        self.assertEqual(before, self.path.read_bytes())
        stored = load_store(self.path)
        self.assertEqual(
            stored[DOI],
            automated | {"citation": "Erratum: Phys. Rev. D 12 (2099) 00123"},
        )
        self.assertEqual(stored["10.9999/manual"], manual)
        self.assertEqual(len(self.path.read_text().splitlines()), 4)

    def test_formatting_cli_uses_explicit_store(self):
        save_store(
            self.path, {DOI: record("Eur.Phys.J.C 12 (2099) 123", source="inspire")}
        )
        with patch("sys.stdout", io.StringIO()) as output:
            cli.main(["format-citations", "--doi-cache", str(self.path)])
        self.assertIn("1 citation(s)", output.getvalue())
        self.assertEqual(
            load_store(self.path)[DOI]["citation"], "Eur. Phys. J. C 12 (2099) 123"
        )

    def test_formatting_uses_starting_page_and_preserves_manual_citations(self):
        values = {}
        for index, (locator, _expected) in enumerate(
            (
                ("101–120", "101"),
                ("101-120", "101"),
                ("E5—E8", "E5"),
                ("00123", "00123"),
                ("P06014", "P06014"),
                ("A1-B9", "A1-B9"),
            )
        ):
            values[f"10.9999/pages-{index}"] = record(
                f"Demo J. 12 (2099) {locator}",
                source="inspire",
            )
        values[DOI] = record("Demo J. 12 (2099) 101–120")
        save_store(self.path, values)
        self.assertEqual(format_citations(self.path), 3)
        entries = load_store(self.path)
        for index, expected in enumerate(
            ("101", "101", "E5", "00123", "P06014", "A1-B9")
        ):
            self.assertEqual(
                entries[f"10.9999/pages-{index}"]["citation"],
                f"Demo J. 12 (2099) {expected}",
            )
        self.assertEqual(entries[DOI]["citation"], "Demo J. 12 (2099) 101–120")

    def test_jhep_rule_is_exact_and_does_not_guess_material(self):
        inferred = infer_citation(JHEP)
        self.assertEqual(inferred["citation"], "JHEP 07 (2099) 999")
        self.assertNotIn("material", inferred)
        for doi in (DOI, "10.1007/JHEP13(2099)999", "10.1007/JHEP07(2099)999-extra"):
            self.assertIsNone(infer_citation(doi))
        self.assertEqual(normalize_doi(f" https://dx.doi.org/{JHEP} "), JHEP.lower())

    def test_doi_resolver_host_aliases_prefixes_and_encoded_urls(self):
        for value in (
            f"https://doi.org/DOI:{JHEP}",
            f"https://www.doi.org/{JHEP}",
            "HTTPS://WWW.DOI.ORG/DOI:10.1007/JHEP07%282099%29999",
            f"http://www.dx.doi.org/{JHEP}?tracking=example#fragment",
            f"DOI: {JHEP}",
        ):
            with self.subTest(value=value):
                self.assertEqual(normalize_doi(value), JHEP.lower())
        with self.assertRaises(ValueError):
            normalize_doi(f"https://example.test/{JHEP}")

    def test_snapshot_skips_malformed_values_without_aborting_valid_dois(self):
        snapshot = self.root / "registry.json"
        snapshot.write_text(
            json.dumps(
                {
                    "entries": {
                        "DEMO-2099-01": {
                            "doi_urls": [
                                f"https://www.doi.org/DOI:{JHEP}",
                                "not-a-doi",
                                42,
                            ]
                        }
                    }
                }
            )
        )
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(snapshot_dois(snapshot), {JHEP.lower()})
        self.assertIn("Skipped 2 malformed DOI values", logs.output[0])

    def test_inference_is_incremental_and_never_contacts_inspire(self):
        with patch(
            "analysis_lister.doi_resolver.InspireClient",
            side_effect=AssertionError("network"),
        ):
            first = resolve_dois([JHEP, JHEP.lower()], self.path)
            before = self.path.read_bytes()
            second = resolve_dois([JHEP], self.path)
        self.assertEqual(first["resolved"], 1)
        self.assertEqual(second["existing"], 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_locked_entries_are_protected_even_on_explicit_refresh(self):
        save_store(self.path, {DOI: record()})
        with patch("analysis_lister.doi_resolver.InspireClient") as client:
            summary = resolve_dois([DOI], self.path, method="inspire", refresh=True)
        client.assert_not_called()
        self.assertEqual(summary["locked"], 1)
        self.assertEqual(load_store(self.path)[DOI], record())

    def test_source_alone_controls_protection_for_legacy_entries(self):
        self.path.write_text(json.dumps({DOI: record(source="manual", locked=False)}))
        with patch("analysis_lister.doi_resolver.InspireClient") as client:
            summary = resolve_dois([DOI], self.path, method="inspire", refresh=True)
        client.assert_not_called()
        self.assertEqual(summary["locked"], 1)
        self.path.write_text(json.dumps({DOI: record(source="inspire", locked=True)}))
        with patch("analysis_lister.doi_resolver.InspireClient") as client:
            client.return_value.fetch.return_value = payload()
            summary = resolve_dois([DOI], self.path, method="inspire", refresh=True)
        self.assertEqual(summary["resolved"], 1)
        self.assertNotIn("locked", load_store(self.path)[DOI])

    def test_inspire_refreshes_unlocked_entries_and_inference_cannot_erase_material(
        self,
    ):
        save_store(self.path, {DOI: record("Old", source="inspire")})
        with patch("analysis_lister.doi_resolver.InspireClient") as client:
            client.return_value.fetch.return_value = payload()
            summary = resolve_dois([DOI], self.path, method="inspire", refresh=True)
        self.assertEqual(summary["resolved"], 1)
        value = load_store(self.path)[DOI]
        self.assertEqual(value["citation"], "Demo J. 12 (2099) 123")
        self.assertEqual(value["inspire_id"], "123456")
        self.assertIn("resolved_at", value)
        save_store(
            self.path,
            {
                JHEP.lower(): record(
                    "Erratum: verified",
                    source="inspire",
                    material="erratum",
                )
            },
        )
        resolve_dois([JHEP], self.path, refresh=True)
        self.assertEqual(
            load_store(self.path)[JHEP.lower()]["citation"], "Erratum: verified"
        )

    def test_failures_are_retryable_and_successes_survive_interruption(self):
        second = "10.9999/other"
        with patch("analysis_lister.doi_resolver.InspireClient") as client:
            client.return_value.fetch.side_effect = [requests.ReadTimeout(), payload()]
            first = resolve_dois([DOI], self.path, method="inspire")
            self.assertNotIn(DOI, load_store(self.path))
            retry = resolve_dois([DOI], self.path, method="inspire")
        self.assertEqual(first["failed"], 1)
        self.assertEqual(retry["resolved"], 1)
        with patch("analysis_lister.doi_resolver.InspireClient") as client:
            client.return_value.fetch.side_effect = KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):
                resolve_dois([second], self.path, method="inspire")
        self.assertIn(DOI, load_store(self.path))

    def test_auto_infers_before_api_and_limit_counts_only_attempts(self):
        with patch("analysis_lister.doi_resolver.InspireClient") as client:
            summary = resolve_dois([JHEP, DOI], self.path, method="auto", limit=1)
        client.assert_not_called()  # The JHEP DOI sorts first.
        self.assertEqual(summary["resolved"], 1)
        self.assertEqual(summary["deferred"], 1)

    def test_snapshot_reads_raw_doi_urls_and_ignores_stale_derived_values(self):
        snapshot = self.root / "registry.json"
        snapshot.write_text(
            json.dumps(
                {
                    "entries": {
                        "DEMO-2099-01": {
                            "doi_urls": [f"https://doi.org/{JHEP}"],
                            "dois": [DOI],
                        }
                    }
                }
            )
        )
        self.assertEqual(snapshot_dois(snapshot), {JHEP.lower()})

    def test_cli_requires_inputs_and_prevents_snapshot_overwrite(self):
        for flags in (
            ["resolve-dois"],
            ["resolve-dois", "--doi", DOI, "--limit", "0"],
            [
                "resolve-dois",
                "--snapshot",
                str(self.path),
                "--doi-cache",
                str(self.path),
            ],
        ):
            with (
                self.subTest(flags=flags),
                patch("sys.stderr", io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                cli.main(flags)
        with patch("sys.stdout", io.StringIO()) as output:
            cli.main(["resolve-dois", "--doi", JHEP, "--doi-cache", str(self.path)])
        self.assertIn("resolved=1", output.getvalue())
        self.assertIn(JHEP.lower(), load_store(self.path))


class InspireTests(unittest.TestCase):
    def test_identical_doi_from_multiple_sources_is_not_an_ambiguity(self):
        data = payload()
        data["metadata"]["dois"][0]["material"] = "publication"
        data["metadata"]["dois"].append(
            {"value": DOI, "source": "arXiv", "material": "publication"}
        )
        self.assertEqual(inspire_citation(DOI, data)["material"], "publication")
        data["metadata"]["dois"][-1]["material"] = "erratum"
        with self.assertRaisesRegex(ValueError, "Conflicting material"):
            inspire_citation(DOI, data)

    def test_matching_material_preserves_article_and_erratum_alignment(self):
        data = payload()
        metadata = data["metadata"]
        correction = "10.9999/erratum"
        metadata["dois"].append({"value": correction, "material": "erratum"})
        metadata["publication_info"].append(
            {
                "journal_title": "Demo J.",
                "journal_volume": "13",
                "year": 2099,
                "artid": "456",
                "material": "erratum",
            }
        )
        self.assertEqual(
            inspire_citation(DOI, data)["citation"], "Demo J. 12 (2099) 123"
        )
        self.assertEqual(
            inspire_citation(correction, data)["citation"],
            "Erratum: Demo J. 13 (2099) 456",
        )

    def test_ambiguous_missing_hidden_and_mismatched_metadata_are_not_guessed(self):
        variants = []
        data = payload()
        data["metadata"]["dois"].append({"value": "10.9999/other"})
        variants.append(data)
        data = payload()
        data["metadata"]["publication_info"].append(
            data["metadata"]["publication_info"][0] | {"journal_volume": "99"}
        )
        variants.append(data)
        data = payload()
        data["metadata"]["publication_info"][0]["hidden"] = True
        variants.append(data)
        data = payload()
        del data["metadata"]["publication_info"][0]["year"]
        variants.append(data)
        variants.extend([payload("10.9999/other"), {}, {"metadata": {"dois": [None]}}])
        for data in variants:
            with self.subTest(data=data), self.assertRaises(ValueError):
                inspire_citation(DOI, data)

    def test_duplicate_and_compatible_partial_publication_rows_are_merged(self):
        data = payload()
        original = data["metadata"]["publication_info"][0]
        data["metadata"]["publication_info"].extend(
            [
                original
                | {"material": "publication", "pubinfo_freetext": "Another source"},
                {"journal_title": "Demo J.", "year": 2099},
                {"material": "publication", "pubinfo_freetext": "Unstructured source"},
            ]
        )
        self.assertEqual(
            inspire_citation(DOI, data)["citation"], "Demo J. 12 (2099) 123"
        )
        data["metadata"]["publication_info"][-2]["year"] = 2098
        with self.assertRaisesRegex(ValueError, "Conflicting publication metadata"):
            inspire_citation(DOI, data)

    def test_unlabelled_duplicate_dois_inherit_only_explicit_consistent_material(self):
        data = payload()
        data["metadata"]["dois"].append({"value": DOI, "material": "erratum"})
        data["metadata"]["publication_info"][0]["material"] = "erratum"
        self.assertEqual(
            inspire_citation(DOI, data)["citation"], "Erratum: Demo J. 12 (2099) 123"
        )

    def test_only_one_unassigned_doi_and_material_can_be_matched(self):
        data = payload()
        correction = "10.9999/correction"
        data["metadata"]["dois"][0]["material"] = "publication"
        data["metadata"]["dois"].append({"value": correction})
        data["metadata"]["publication_info"].append(
            {
                "journal_title": "Demo J.",
                "journal_volume": "13",
                "year": 2099,
                "artid": "456",
                "material": "erratum",
            }
        )
        self.assertEqual(
            inspire_citation(correction, data)["citation"],
            "Erratum: Demo J. 13 (2099) 456",
        )
        data["metadata"]["dois"].append({"value": "10.9999/another"})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            inspire_citation(correction, data)

    def test_explicit_page_ranges_are_compatible_with_an_additional_article_id(self):
        data = payload()
        data["metadata"]["publication_info"] = [
            {
                "journal_title": "Demo J.",
                "journal_volume": "12",
                "year": 2099,
                "artid": "999",
                "page_start": "101",
                "page_end": "120",
            },
            {
                "journal_title": "Demo J.",
                "journal_volume": "12",
                "year": 2099,
                "page_start": "101",
                "page_end": "120",
            },
        ]
        self.assertEqual(
            inspire_citation(DOI, data)["citation"], "Demo J. 12 (2099) 101"
        )

    @patch("analysis_lister.doi_resolver.time.sleep")
    @patch("analysis_lister.doi_resolver.requests.Session")
    def test_http_client_uses_verified_tls_timeouts_and_bounded_rate_limit_retry(
        self, session, sleep
    ):
        session.return_value.get.side_effect = [
            response(429, headers={"Retry-After": "6"}),
            response(),
        ]
        client = InspireClient()
        self.assertEqual(client.fetch(DOI), payload())
        self.assertEqual(session.return_value.get.call_count, 2)
        self.assertIn(
            ((6,), {}), [(call.args, call.kwargs) for call in sleep.call_args_list]
        )
        self.assertEqual(session.return_value.get.call_args.kwargs["timeout"], (10, 30))
        self.assertIs(session.return_value.get.call_args.kwargs["verify"], True)
        client.close()
        session.return_value.close.assert_called_once()

    @patch("analysis_lister.doi_resolver.time.sleep")
    @patch("analysis_lister.doi_resolver.requests.Session")
    def test_tls_errors_are_not_retried_and_long_retry_after_is_deferred(
        self, session, sleep
    ):
        session.return_value.get.side_effect = requests.exceptions.SSLError("synthetic")
        with self.assertRaises(requests.exceptions.SSLError):
            InspireClient().fetch(DOI)
        self.assertEqual(session.return_value.get.call_count, 1)
        sleep.assert_not_called()
        session.return_value.get.side_effect = None
        session.return_value.get.return_value = response(
            429, headers={"Retry-After": "120"}
        )
        with self.assertRaisesRegex(ValueError, "longer pause"):
            InspireClient().fetch(DOI)
        sleep.assert_not_called()

    @patch("analysis_lister.doi_resolver.requests.Session")
    def test_not_found_is_unresolved(self, session):
        session.return_value.get.return_value = response(404)
        self.assertIsNone(InspireClient().fetch(DOI))
