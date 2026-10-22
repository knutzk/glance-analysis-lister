# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Curated DOI/citation alignment using invented publication metadata."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis_lister.doi_resolver import snapshot_dois
from analysis_lister.publication_dois import enrich_paper, paper_dois

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
