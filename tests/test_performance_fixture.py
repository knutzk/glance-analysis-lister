# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""The scale benchmark must retain real curated identities and relationships."""

import json
import unittest
from collections import Counter
from pathlib import Path
from runpy import run_path

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

ROOT = Path(__file__).resolve().parents[1]
synthetic_registry = run_path(str(ROOT / "tests/browser/performance_fixture.py"))[
    "synthetic_registry"
]


class PerformanceFixtureTests(unittest.TestCase):
    def test_scale_retains_collections_filter_mix_and_supersession(self):
        data = synthetic_registry(12)
        view = prepare_group(
            CuratedRegistry(data),
            GroupProfile(
                "DEMO", publication_policy=PublicationPolicy(groups=("DEMO",))
            ),
        )
        self.assertEqual(len(view.ongoing), 12)
        self.assertEqual(
            Counter(row.resource for row in view.archive),
            {"papers": 12, "confnotes": 12, "pubnotes": 12},
        )
        for resource in ("analyses", "papers", "confnotes", "pubnotes"):
            identity = (
                "temporaryReferenceCode"
                if resource.endswith("notes")
                else "referenceCode"
            )
            by_id = {record[identity]: record for record in data[resource]}
            self.assertEqual(len(by_id), 12)
            self.assertEqual(
                sum(
                    "Tracking" in record["metadata"]["gal_keywords"]
                    for record in by_id.values()
                ),
                6,
            )
            if resource.endswith("notes"):
                self.assertEqual(
                    len({record["finalReferenceCode"] for record in by_id.values()}), 12
                )
                self.assertEqual(
                    sum(bool(record.get("supersededBy")) for record in by_id.values()),
                    3,
                )
                for record in by_id.values():
                    for link in record.get("supersededBy", []):
                        target = by_id[link["referenceCode"]]
                        self.assertNotEqual(target[identity], record[identity])
                        self.assertEqual(
                            int(target[identity].split("-")[-1]),
                            int(record[identity].split("-")[-1]) + 1,
                        )

    def test_generation_is_deterministic_and_leaves_demo_unchanged(self):
        fixture = ROOT / "examples/synthetic_registry.json"
        original = fixture.read_bytes()
        first = synthetic_registry(8)
        self.assertEqual(first, synthetic_registry(8))
        first["analyses"][0]["metadata"]["gal_keywords"].append("Mutation")
        self.assertNotIn("Mutation", first["analyses"][4]["metadata"]["gal_keywords"])
        self.assertEqual(fixture.read_bytes(), original)
        self.assertEqual(json.loads(original)["counts"]["analyses"], 4)

    def test_partial_cohorts_are_rejected(self):
        for size in (-4, 0, 1, 5):
            with self.subTest(size=size), self.assertRaises(ValueError):
                synthetic_registry(size)


if __name__ == "__main__":
    unittest.main()
