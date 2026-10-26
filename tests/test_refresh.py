# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise refresh sequencing, preflight and real offline construction/rendering."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_api import client_for

from analysis_lister import cli


class RefreshTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api = self.root / "api.json"
        self.curated = self.root / "curated.json"
        self.pages = self.root / "pages"

    def command(self, *groups):
        return [
            "refresh",
            "--groups",
            *groups,
            "--api-snapshot",
            str(self.api),
            "--snapshot",
            str(self.curated),
            "--output-dir",
            str(self.pages),
            "--color",
            "never",
        ]

    def test_real_offline_pipeline_single_and_multiple_groups(self):
        for groups in (("TOPQ",), ("TOPQ", "HIGP")):
            with (
                self.subTest(groups=groups),
                patch("stare.Glance") as glance,
                patch("stare.auth.TokenManager") as manager,
                patch("stare.settings.StareSettings") as settings,
                redirect_stdout(io.StringIO()) as output,
                redirect_stderr(io.StringIO()),
            ):
                settings.return_value.base_url = "https://example.test/api"
                client = client_for()
                for resource in ("analyses", "papers", "confnotes", "pubnotes"):
                    for model in (
                        getattr(client, resource).search(offset=0, limit=3).results
                    ):
                        model.model_dump.return_value["groups"] = {
                            "leadingGroup": {"name": "TOPQ"},
                            "otherGroups": [{"name": "HIGP"}],
                        }
                glance.return_value.__enter__.return_value = client
                cli.main([*self.command(*groups), "--login", "--page-size", "250"])
                manager.return_value.login.assert_called_once_with()
                glance.assert_called_once()
                self.assertTrue(self.api.is_file())
                self.assertTrue(self.curated.is_file())
                for group in groups:
                    directory = (
                        self.pages if len(groups) == 1 else self.pages / group.lower()
                    )
                    for name in (
                        "ongoing.md",
                        "papers.md",
                        "confnotes.md",
                        "pubnotes.md",
                        "view-report.json",
                        "assets/gal-common.js",
                    ):
                        self.assertTrue((directory / name).is_file(), name)
                    self.assertIn(
                        str(directory / "view-report.json"), output.getvalue()
                    )
                self.assertIn("Refresh complete", output.getvalue())

    def test_invalid_plans_fail_before_authentication_or_writes(self):
        bad_config = self.root / "bad.toml"
        bad_config.write_text("invalid [")
        cases = [
            self.command("TOPQ", "TOPQ"),
            self.command("../TOPQ"),
            [*self.command("TOPQ"), "--snapshot", str(self.api)],
            [*self.command("TOPQ"), "--api-snapshot", str(self.pages / "papers.md")],
            [*self.command("TOPQ"), "--api-snapshot", str(self.pages)],
            [*self.command("TOPQ"), "--curation-config", str(bad_config)],
            [
                *self.command("TOPQ"),
                "--api-snapshot",
                str(bad_config),
                "--curation-config",
                str(bad_config),
            ],
        ]
        for command in cases:
            with (
                self.subTest(command=command),
                patch("analysis_lister.cli._run_download_api") as download,
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                cli.main(command)
            self.assertEqual(error.exception.code, 1)
            download.assert_not_called()
            self.assertFalse(self.api.exists())

    def test_failures_stop_remaining_stages_without_completion_summary(self):
        for failure in ("download", "build", "render"):
            events = []

            def step(name, events=events, failure=failure):
                def execute(*args):
                    events.append(name)
                    if failure == name:
                        raise ValueError("synthetic failure")
                    return {}

                return execute

            with (
                self.subTest(failure=failure),
                patch(
                    "analysis_lister.cli._run_download_api",
                    side_effect=step("download"),
                ),
                patch(
                    "analysis_lister.cli._run_build_registry", side_effect=step("build")
                ),
                patch(
                    "analysis_lister.refresh.render_group", side_effect=step("render")
                ),
                redirect_stdout(io.StringIO()) as output,
                redirect_stderr(io.StringIO()) as errors,
                self.assertRaises(SystemExit),
            ):
                cli.main(self.command("TOPQ", "HIGP"))
            self.assertEqual(
                events,
                ["download", "build", "render"][
                    : ["download", "build", "render"].index(failure) + 1
                ],
            )
            self.assertNotIn("Refresh complete", output.getvalue())
            self.assertIn(
                "Completed outputs are retained", " ".join(errors.getvalue().split())
            )

    def test_options_reach_both_protected_stages(self):
        with (
            patch("analysis_lister.cli._run_download_api") as download,
            patch("analysis_lister.cli._run_build_registry") as build,
            patch("analysis_lister.refresh.render_group", return_value={}),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            cli.main(
                [
                    *self.command("TOPQ"),
                    "--allow-count-drop",
                    "--page-size",
                    "123",
                    "--login",
                ]
            )
        downloaded = download.call_args.args[0]
        built = build.call_args.args[0]
        self.assertEqual(downloaded.output, self.api)
        self.assertEqual(downloaded.page_size, 123)
        self.assertTrue(downloaded.login)
        self.assertTrue(downloaded.allow_count_drop)
        self.assertTrue(built.allow_count_drop)
        self.assertEqual(built.api_snapshot, self.api)
        self.assertEqual(built.output, self.curated)
