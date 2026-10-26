# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Curated DOI/citation alignment using invented publication metadata."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis_lister.citations.resolver import snapshot_dois
from analysis_lister.registry.publication_dois import enrich_paper, paper_dois

ORIGINAL = "10.1007/jhep01(2099)001"
CORRECTION = "10.1007/jhep02(2099)002"


def paper(*urls):
    return {
        "referenceCode": "DEMO-2099-01",
        "publicationPhase": {
            "finalJournalPublicationUrls": [{"url": url} for url in urls]
        },
    }


class PublicationDoiTests(unittest.TestCase):
    def test_conflicting_label_is_ignored_without_changing_source(self):
        record = paper("https://doi.org/" + CORRECTION)
        link = record["publicationPhase"]["finalJournalPublicationUrls"][0]
        link["label"] = "DOI:" + ORIGINAL
        original_link = link.copy()
        with self.assertNoLogs("analysis_lister.registry.publication_dois"):
            self.assertEqual(paper_dois(record), ([CORRECTION], 0))
        self.assertEqual(link, original_link)

    def test_equivalent_label_and_url_do_not_warn(self):
        record = paper("http://dx.doi.org/" + ORIGINAL)
        record["publicationPhase"]["finalJournalPublicationUrls"][0]["label"] = (
            "DOI:" + ORIGINAL.upper()
        )
        with self.assertNoLogs("analysis_lister.registry.publication_dois"):
            self.assertEqual(paper_dois(record), ([ORIGINAL], 0))

    def test_link_conflict_does_not_suppress_ambiguous_order_warning(self):
        record = paper(
            "https://doi.org/10.1234/example-b", "https://doi.org/10.1234/example-c"
        )
        record["publicationPhase"]["finalJournalPublicationUrls"][0]["label"] = (
            "DOI:10.1234/example-a"
        )
        with self.assertLogs("analysis_lister", level="WARNING") as logs:
            entries, malformed = enrich_paper(record, {})
        self.assertEqual(malformed, 0)
        self.assertEqual(len(entries), 2)
        self.assertFalse(any("label" in m for m in logs.output))
        self.assertTrue(any("ambiguous DOI order" in m for m in logs.output))

    def test_normalizes_and_deduplicates_doi_links_without_treating_inspire_as_doi(
        self,
    ):
        record = paper(
            "https://doi.org/" + ORIGINAL.upper(),
            "http://dx.doi.org/" + ORIGINAL,
            "https://inspirehep.net/literature/123",
            "https://doi.org/invalid",
        )
        self.assertEqual(paper_dois(record), ([ORIGINAL], 1))

    def test_publisher_paths_supply_dois_independently_of_labels(self):
        record = paper()
        record["publicationPhase"]["finalJournalPublicationUrls"] = [
            {"label": "DOI:" + ORIGINAL, "url": "https://example.test/literature/123"},
            {"label": "Publisher", "url": "https://example.test/doi/" + ORIGINAL},
            {"label": "Publisher", "url": "https://example.test/doi/" + CORRECTION},
        ]
        self.assertEqual(paper_dois(record), ([ORIGINAL, CORRECTION], 0))
        entries, _ = enrich_paper(record, {ORIGINAL: "Invented citation"})
        self.assertEqual(entries[0]["citation"], "Invented citation")
        self.assertEqual(entries[1]["doi"], CORRECTION)

    def test_label_only_doi_is_not_a_fallback(self):
        record = paper("https://example.test/science/article/pii/INVENTED")
        record["publicationPhase"]["finalJournalPublicationUrls"][0]["label"] = (
            "Errratum: DOI:" + ORIGINAL
        )
        with self.assertNoLogs("analysis_lister.registry.publication_dois"):
            self.assertEqual(paper_dois(record), ([], 0))

    def test_publisher_paths_with_embedded_dois(self):
        record = paper(
            "https://example.test/article/" + ORIGINAL + "?tracking=ignored",
            "https://example.test/doi/full/" + CORRECTION,
            "https://example.test/science/article/pii/INVENTED",
        )
        self.assertEqual(paper_dois(record), ([ORIGINAL, CORRECTION], 0))

    def test_each_correction_keeps_its_citation_and_provenance(self):
        record = paper("https://doi.org/" + CORRECTION, "https://doi.org/" + ORIGINAL)
        links = record["publicationPhase"]["finalJournalPublicationUrls"].copy()
        citations = {
            ORIGINAL: {
                "citation": "Original citation",
                "source": "manual",
                "material": "publication",
                "locked": True,
            },
            CORRECTION: {
                "citation": "Correction citation",
                "source": "inspire",
                "material": "erratum",
                "source_url": "https://example.test/correction",
            },
        }
        entries, invalid = enrich_paper(record, citations)
        self.assertEqual(invalid, 0)
        self.assertEqual(record["publicationPhase"]["gal_dois"], entries)
        self.assertNotIn("dois", record["publicationPhase"])
        self.assertEqual([entry["doi"] for entry in entries], [ORIGINAL, CORRECTION])
        self.assertEqual(
            [entry["citation"] for entry in entries],
            ["Original citation", "Correction citation"],
        )
        self.assertEqual(entries[1]["material"], "erratum")
        self.assertEqual(entries[1]["source_url"], "https://example.test/correction")
        self.assertNotIn("locked", entries[0])
        self.assertTrue(citations[ORIGINAL]["locked"])
        self.assertEqual(
            record["publicationPhase"]["finalJournalPublicationUrls"], links
        )

    def test_unresolved_doi_remains_available_without_fabricated_citation(self):
        record = paper("https://doi.org/" + ORIGINAL)
        entries, _ = enrich_paper(record, {})
        self.assertEqual(
            entries,
            [
                {
                    "doi": ORIGINAL,
                    "url": "https://doi.org/" + ORIGINAL,
                    "resolved": False,
                }
            ],
        )

    def test_lowercase_normalization_preserves_date_based_correction_order(self):
        record = paper("https://doi.org/" + CORRECTION, "https://doi.org/" + ORIGINAL)
        entries, _ = enrich_paper(record, {})
        self.assertEqual([entry["doi"] for entry in entries], [ORIGINAL, CORRECTION])

    def test_resolver_reads_source_urls_in_both_new_formats(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            for schema in ("glance-api-registry", "glance-curated-registry"):
                record = paper("https://doi.org/" + ORIGINAL)
                record["publicationPhase"]["gal_dois"] = [{"doi": CORRECTION}]
                path.write_text(json.dumps({"schema": schema, "papers": [record]}))
                self.assertEqual(snapshot_dois(path), {ORIGINAL})
