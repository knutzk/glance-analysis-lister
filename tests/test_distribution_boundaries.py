# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Known local/private names must be rejected in either distribution format."""

import unittest

from scripts.check_distribution import check_public_paths


class DistributionBoundaryTests(unittest.TestCase):
    def test_forbidden_sentinels_are_rejected(self):
        for name in (
            "AGENTS.md",
            ".python-version",
            "cookies.json",
            "examples/cookies.json",
            "glance_api_registry.json",
            "glance_curated_registry.json",
            "downloads/papers.csv",
            "debug/response.html",
            "pages/topq/papers.md",
            ".cache/docs-group-preview/site/index.html",
            "docs/analyses/papers.md",
            "examples/demo/work/papers.md",
            "examples/demo/.cache/state.txt",
            "browser-report/failure.png",
            "coverage-report/index.html",
            "public-api-report/changes.md",
            "analysis_lister/events.py",
            "analysis_lister/event_labels.py",
            "tests/test_events.py",
            ".venv/pyvenv.cfg",
            "site/index.html",
            ".refresh-123/staged.json",
            ".html-download-in-progress",
        ):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(AssertionError, "Forbidden private/local paths"),
            ):
                check_public_paths([name], "synthetic artifact")

    def test_public_resources_and_installed_data_paths_are_allowed(self):
        check_public_paths(
            [
                "analysis_lister/registry/schemas/curated.schema.json",
                "examples/synthetic_registry.json",
                "tests/fixtures/curated/invented.json",
                "json/doi_metadata.json",
                "json/pubnote_identifiers.json",
                "../../../share/glance-analysis-lister/doi_metadata.json",
                "../../../share/glance-analysis-lister/pubnote_identifiers.json",
                "analysis_lister/downloaders/certs/README.md",
                "analysis_lister/downloaders/certs/intermediate.pem",
                "analysis_lister/_source_revision.txt",
                "docs/images/ongoing.png",
                "package.dist-info/licenses/LICENCE",
            ],
            "synthetic artifact",
        )
