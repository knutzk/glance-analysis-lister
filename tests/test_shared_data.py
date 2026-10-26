# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Shared policies are available without consumer-owned configuration."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister.cli import parser
from analysis_lister.views.curation import (
    default_curation_path,
    load_publication_policy,
)


class SharedDataTests(unittest.TestCase):
    def test_render_defaults_to_shared_policy_and_accepts_override(self):
        args = parser().parse_args(["render-group", "--group", "TOPQ"])
        self.assertEqual(args.curation_config, default_curation_path())
        self.assertIsNotNone(load_publication_policy(args.curation_config, "TOPQ"))
        args = parser().parse_args(
            ["render-group", "--group", "TOPQ", "--curation-config", "custom.toml"]
        )
        self.assertEqual(args.curation_config, Path("custom.toml"))

    def test_installed_policy_location(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "share/glance-analysis-lister/publication-curation.toml"
            installed.parent.mkdir(parents=True)
            installed.write_text('[groups.DEMO]\ngroups = ["DEMO"]\n')
            with (
                patch(
                    "analysis_lister.views.curation.__file__", str(root / "a/b/c.py")
                ),
                patch("analysis_lister.views.curation.distribution") as distribution,
            ):
                distribution.return_value.files = [installed.relative_to(root)]
                distribution.return_value.locate_file.side_effect = lambda path: (
                    root / path
                )
                self.assertEqual(default_curation_path(), installed)
                self.assertEqual(
                    load_publication_policy(installed, "DEMO").groups, ("DEMO",)
                )
