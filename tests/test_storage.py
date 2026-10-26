# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Atomic text publication, permissions, and failure recovery."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister.storage import atomic_write_text


class RegistryWriteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "registry.json"
        self.old = '{"previous": true}\n'
        self.path.write_text(self.old)
        self.candidate = '{"synthetic": true}\n'

    def test_complete_snapshot_is_published(self):
        self.path.chmod(0o640)
        atomic_write_text(self.path, self.candidate)
        self.assertEqual(
            json.loads(self.path.read_text()),
            {"synthetic": True},
        )
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_first_snapshot_creates_nested_parent_directories(self):
        destination = self.path.parent / "new" / "json" / "registry.json"
        atomic_write_text(destination, self.candidate)
        self.assertEqual(json.loads(destination.read_text()), {"synthetic": True})
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_failed_flush_or_replace_preserves_previous_snapshot(self):
        for target in ("analysis_lister.storage.os.fsync", "pathlib.Path.replace"):
            with (
                self.subTest(target=target),
                patch(target, side_effect=OSError("disk failure")),
            ):
                with self.assertRaises(OSError):
                    atomic_write_text(self.path, self.candidate)
                self.assertEqual(self.path.read_text(), self.old)
                self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == "__main__":
    unittest.main()
