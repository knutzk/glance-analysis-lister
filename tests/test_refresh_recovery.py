# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Recover real saved outputs after synthetic retrieval and publication failures."""

import io
import json
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_api import client_for

from analysis_lister import cli
from analysis_lister.downloaders.api import collect_registry, publish_registry

GROUPS = ("DEMO", "SECOND", "THIRD")
RESOURCES = ("analyses", "papers", "confnotes", "pubnotes")


class RefreshRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api = self.root / "api.json"
        self.curated = self.root / "curated.json"
        self.pages = self.root / "pages"
        self.policy = self.root / "policy.toml"
        self.policy.write_text(
            "\n".join(f'[groups.{group}]\ngroups = ["{group}"]' for group in GROUPS)
        )
        self.stdout = self.enterContext(redirect_stdout(io.StringIO()))
        self.stderr = self.enterContext(redirect_stderr(io.StringIO()))
        self.enterContext(
            patch(
                "socket.socket.connect",
                side_effect=AssertionError("unexpected network"),
            )
        )
        with self.retrieval(self.client("Before")):
            cli.main(self.refresh_command())
        self.before = self.saved_files(self.root)
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()

    @staticmethod
    def saved_files(root):
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    @staticmethod
    def client(title, count=3):
        client = client_for(count)
        for resource in RESOURCES:
            for model in (
                getattr(client, resource).search(offset=0, limit=count).results
            ):
                model.model_dump.return_value.update(
                    shortTitle=title,
                    status="Phase 0 Active"
                    if resource == "analyses"
                    else "Phase 1 Active",
                    groups={
                        "leadingGroup": {"name": GROUPS[0]},
                        "otherGroups": [{"name": group} for group in GROUPS[1:]],
                    },
                )
        return client

    @contextmanager
    def retrieval(self, client):
        with (
            patch("stare.Glance") as glance,
            patch("stare.auth.TokenManager"),
            patch("stare.settings.StareSettings") as settings,
        ):
            settings.return_value.base_url = "https://example.test/api"
            glance.return_value.__enter__.return_value = client
            yield

    @contextmanager
    def offline(self):
        with (
            patch("stare.Glance", side_effect=AssertionError("unexpected retrieval")),
            patch(
                "stare.auth.TokenManager",
                side_effect=AssertionError("unexpected login"),
            ),
        ):
            yield

    def refresh_command(self):
        return [
            "refresh",
            "--groups",
            *GROUPS,
            "--api-snapshot",
            str(self.api),
            "--snapshot",
            str(self.curated),
            "--output-dir",
            str(self.pages),
            "--curation-config",
            str(self.policy),
            "--page-size",
            "2",
            "--color",
            "never",
        ]

    def build(self, *options):
        cli.main(
            [
                "build-registry",
                "--api-snapshot",
                str(self.api),
                "--output",
                str(self.curated),
                "--color",
                "never",
                *options,
            ]
        )

    def render(self, group, output=None):
        cli.main(
            [
                "render-group",
                "--group",
                group,
                "--snapshot",
                str(self.curated),
                "--output-dir",
                str(output or self.pages / group.lower()),
                "--curation-config",
                str(self.policy),
                "--color",
                "never",
            ]
        )

    def assert_stopped(self, stage):
        self.assertNotIn("Refresh complete", self.stdout.getvalue())
        self.assertIn(f"Refresh stopped during {stage}", self.stderr.getvalue())

    def test_interrupted_pagination_preserves_outputs_and_can_restart(self):
        client = self.client("After")
        first = client.analyses.search(offset=0, limit=2)
        client.analyses.search.side_effect = [first, KeyboardInterrupt()]
        with self.retrieval(client), self.assertRaises(KeyboardInterrupt):
            cli.main(self.refresh_command())
        self.assertEqual(self.saved_files(self.root), self.before)
        self.assert_stopped("API download")

        with self.retrieval(self.client("After")):
            cli.main(self.refresh_command())
        self.assertEqual(
            json.loads(self.api.read_bytes())["counts"], dict.fromkeys(RESOURCES, 3)
        )
        self.assertIn("After", (self.pages / "demo/ongoing.md").read_text())
        self.assertIn("Refresh complete", self.stdout.getvalue())

    def test_download_count_drop_preserves_all_outputs_until_explicit_override(self):
        with (
            self.retrieval(self.client("After", 1)),
            self.assertRaises(SystemExit) as error,
        ):
            cli.main(self.refresh_command())
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(self.saved_files(self.root), self.before)
        self.assert_stopped("API download")
        self.assertIn("20%", self.stderr.getvalue())

        with self.retrieval(self.client("After", 1)):
            cli.main([*self.refresh_command(), "--allow-count-drop"])
        for path in (self.api, self.curated):
            self.assertEqual(
                json.loads(path.read_bytes())["counts"], dict.fromkeys(RESOURCES, 1)
            )

    def test_build_count_guard_is_independent_and_can_resume_offline(self):
        # The API destination can already contain fewer records than the curated one.
        candidate = collect_registry(self.client("After", 1))
        candidate["source"]["base_url"] = "https://example.test/api"
        publish_registry(candidate, self.api, allow_count_drop=True)
        with (
            self.retrieval(self.client("After", 1)),
            self.assertRaises(SystemExit) as error,
        ):
            cli.main(self.refresh_command())
        self.assertEqual(error.exception.code, 1)
        self.assert_stopped("registry build")
        self.assertEqual(self.curated.read_bytes(), self.before["curated.json"])
        self.assertEqual(
            self.saved_files(self.pages),
            {
                name.removeprefix("pages/"): value
                for name, value in self.before.items()
                if name.startswith("pages/")
            },
        )
        downloaded = self.api.read_bytes()
        with self.offline():
            self.build("--allow-count-drop")
            for group in GROUPS:
                self.render(group)
        self.assertEqual(self.api.read_bytes(), downloaded)
        self.assertEqual(
            json.loads(self.curated.read_bytes())["counts"], dict.fromkeys(RESOURCES, 1)
        )

    def test_interrupted_registry_publication_retains_download_for_offline_recovery(
        self,
    ):
        replace = Path.replace

        def interrupt(source, target):
            if target == self.curated:
                raise KeyboardInterrupt()
            return replace(source, target)

        with (
            self.retrieval(self.client("After")),
            patch.object(Path, "replace", interrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            cli.main(self.refresh_command())
        self.assert_stopped("registry build")
        self.assertNotEqual(self.api.read_bytes(), self.before["api.json"])
        remaining = self.saved_files(self.root)
        remaining.pop("api.json")
        self.assertEqual(
            remaining,
            {name: value for name, value in self.before.items() if name != "api.json"},
        )
        downloaded = self.api.read_bytes()
        with self.offline():
            self.build()
            for group in GROUPS:
                self.render(group)
        self.assertEqual(self.api.read_bytes(), downloaded)
        self.assertIn("After", (self.pages / "demo/ongoing.md").read_text())

    def test_partial_group_render_can_resume_without_rewriting_completed_groups(self):
        replace = Path.replace

        def fail_second_group(source, target):
            if target == self.pages / "second/papers.md":
                raise OSError("invented publication failure")
            return replace(source, target)

        with (
            self.retrieval(self.client("After")),
            patch.object(Path, "replace", fail_second_group),
            self.assertRaises(SystemExit) as error,
        ):
            cli.main(self.refresh_command())
        self.assertEqual(error.exception.code, 1)
        self.assert_stopped("rendering SECOND")
        self.assertNotEqual(
            (self.pages / "second/ongoing.md").read_bytes(),
            self.before["pages/second/ongoing.md"],
        )
        self.assertEqual(
            (self.pages / "second/papers.md").read_bytes(),
            self.before["pages/second/papers.md"],
        )
        for name, content in self.before.items():
            if name.startswith("pages/third/"):
                self.assertEqual((self.root / name).read_bytes(), content)
        self.assertFalse(list(self.root.rglob("*.tmp")))
        snapshots = (self.api.read_bytes(), self.curated.read_bytes())
        completed = {
            path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
            for path in (self.pages / "demo").rglob("*")
            if path.is_file()
        }
        with self.offline():
            for group in GROUPS[1:]:
                self.render(group)
            for group in GROUPS:
                fresh = self.root / "fresh" / group.lower()
                self.render(group, fresh)
                self.assertEqual(
                    self.saved_files(self.pages / group.lower()),
                    self.saved_files(fresh),
                )
        self.assertEqual((self.api.read_bytes(), self.curated.read_bytes()), snapshots)
        for path, state in completed.items():
            self.assertEqual(
                (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino), state
            )
