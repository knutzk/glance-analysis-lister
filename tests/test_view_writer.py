# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Unchanged-file publication and snapshot collision protection."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from view_fixtures import analysis, snapshot

from grove.views.build import render_group
from grove.views.profiles import GroupProfile, PublicationPolicy
from grove.views.writer import write_documents


def states(directory):
    return {
        path.relative_to(directory).as_posix(): (
            path.stat().st_ino,
            path.stat().st_mtime_ns,
            path.read_bytes(),
        )
        for path in directory.rglob("*")
        if path.is_file()
    }


class ViewWriterTests(unittest.TestCase):
    def test_identical_render_preserves_mtimes_inodes_and_unrelated_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "registry.json", root / "pages"
            source.write_text(json.dumps(snapshot(analysis(1))))
            profile = GroupProfile(
                "DEMO", publication_policy=PublicationPolicy(groups=("DEMO",))
            )
            render_group(source, output, profile)
            keep = output / "hand-written.txt"
            keep.write_text("preserve me")
            for path in output.rglob("*"):
                if path.is_file():
                    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
            before = states(output)
            with (
                patch(
                    "grove.views.writer.atomic_write_text",
                    side_effect=AssertionError("unchanged output must not be written"),
                ),
                self.assertLogs("grove.views.build", level="INFO") as logs,
            ):
                render_group(source, output, profile)
            self.assertIn("0 written, 13 unchanged", "\n".join(logs.output))
            self.assertEqual(states(output), before)
            (output / "papers.md").write_text("locally changed")
            (output / "assets/grove-common.css").unlink()
            with self.assertLogs("grove.views.build", level="INFO") as logs:
                render_group(source, output, profile)
            self.assertIn("2 written, 11 unchanged", "\n".join(logs.output))
            after = states(output)
            for name in before:
                if name in {"papers.md", "assets/grove-common.css"}:
                    self.assertEqual(after[name][2], before[name][2])
                else:
                    self.assertEqual(after[name], before[name])

    def test_snapshot_collision_is_rejected_even_for_identical_content(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers.md"
            source.write_text("identical")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                write_documents(
                    root,
                    {"ongoing.md": "new", "papers.md": "identical"},
                    snapshot=source,
                )
            self.assertFalse((root / "ongoing.md").exists())
            self.assertEqual(source.read_text(), "identical")
