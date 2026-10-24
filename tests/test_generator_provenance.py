# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Generated notices identify source code and inputs without time-based churn."""

import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister.provenance import (
    REVISION_FILE,
    asset_provenance,
    generator_revision,
    markdown_provenance,
)

COMMIT = "a" * 40


class GeneratorProvenanceTests(unittest.TestCase):
    def test_markdown_keeps_front_matter_first_and_sanitizes_snapshot_name(self):
        source = "---\nhide:\n  - toc\n---\n\n# Papers\n"
        result = markdown_provenance(
            source,
            revision=COMMIT + "-dirty",
            snapshot="/private/input-->.json",
            sha256="b" * 64,
        )
        self.assertTrue(result.startswith("---\nhide:\n  - toc\n---\n\n<!--\n"))
        self.assertIn("Generator Git commit: " + COMMIT + "-dirty", result)
        self.assertIn("Registry SHA-256: " + "b" * 64, result)
        self.assertNotIn("/private/", result)
        self.assertEqual(result.count("-->"), 1)
        self.assertTrue(result.endswith("# Papers\n"))
        self.assertEqual(
            result,
            markdown_provenance(
                source,
                revision=COMMIT + "-dirty",
                snapshot="/private/input-->.json",
                sha256="b" * 64,
            ),
        )

    def test_asset_notice_preserves_spdx_and_has_no_registry_data(self):
        source = "/* SPDX-FileCopyrightText: 2099 Invented Author\n * SPDX-License-Identifier: GPL-3.0-only */\nbody { margin: 0; }\n"
        result = asset_provenance(source, revision=COMMIT)
        self.assertTrue(result.startswith(source.split("*/")[0] + "*/"))
        self.assertIn("Source Git commit: " + COMMIT, result)
        self.assertNotIn("Registry", result)
        self.assertTrue(result.endswith("body { margin: 0; }\n"))

    def test_installed_revision_does_not_use_the_consumers_repository(self):
        with TemporaryDirectory() as directory:
            consumer = Path(directory)
            (consumer / ".git").mkdir()
            package_root = consumer / "installed"
            recorded = package_root / "analysis_lister" / REVISION_FILE
            recorded.parent.mkdir(parents=True)
            recorded.write_text(COMMIT + "-dirty\n")
            with patch(
                "analysis_lister.provenance.subprocess.check_output",
                side_effect=AssertionError("consumer git must not be inspected"),
            ):
                self.assertEqual(generator_revision(package_root), COMMIT + "-dirty")
                recorded.unlink()
                self.assertEqual(generator_revision(package_root), "unknown")

    @unittest.skipUnless(shutil.which("git"), "Git required for checkout provenance")
    def test_checkout_commit_dirty_changes_and_new_source_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", str(root), *args],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()

            git("init", "-q")
            source = root / "tracked.py"
            source.write_text("original\n")
            git("add", "tracked.py")
            git(
                "-c",
                "user.name=Invented Author",
                "-c",
                "user.email=invented@example.test",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Invented fixture",
            )
            commit = git("rev-parse", "HEAD")
            self.assertEqual(generator_revision(root), commit)
            (root / ".DS_Store").write_text("unrelated")
            self.assertEqual(generator_revision(root), commit)
            source.write_text("changed\n")
            self.assertEqual(generator_revision(root), commit + "-dirty")
            source.write_text("original\n")
            (root / "analysis_lister").mkdir()
            (root / "analysis_lister/new.py").write_text("new source\n")
            self.assertEqual(generator_revision(root), commit + "-dirty")
