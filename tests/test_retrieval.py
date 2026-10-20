# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Synthetic retrieval scopes, query propagation and dataset boundaries."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister import cli, download, refresh
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.retrieval import (
    SCOPE_FILENAME,
    RetrievalScope,
    check_scope,
    load_scope,
    read_scope,
)

HTML = "<table><tr><th>Reference Code</th></tr><tr><td>DEMO-2099-01</td></tr></table>"
CONFIG = """name = "Synthetic group"
[selection]
field = "subgroups"
operator = "contains"
values = [901, 902, 903, 904]
"""


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "scope.toml"
        self.config.write_text(CONFIG)
        self.scope = load_scope(self.config)
        self.tasks = tuple(
            download.DownloadTable(
                name,
                f"https://example.test/{name}",
                ("Reference Code",),
                "reference_code",
            )
            for name in ("analyses", "papers", "confnotes", "pubnotes")
        )

    def test_default_exactly_preserves_historical_filters(self):
        params = load_scope().query_params()
        self.assertEqual(len(params), 12)
        for index, value in enumerate((80, 198, 205)):
            self.assertEqual(params[f"c[{index}][i]"], index)
            self.assertEqual(params[f"c[{index}][p]"], "subgroups")
            self.assertEqual(params[f"c[{index}][o]"], "contains")
            self.assertEqual(params[f"c[{index}][v]"], value)

    def test_invalid_configuration_fails_before_credentials_or_work(self):
        for invalid in (
            CONFIG.replace("[901, 902, 903, 904]", "[]"),
            CONFIG.replace("[901, 902, 903, 904]", "[true]"),
            CONFIG.replace("[901, 902, 903, 904]", "[-1]"),
            CONFIG.replace("[901, 902, 903, 904]", '[""]'),
            CONFIG.replace("[901, 902, 903, 904]", "[[901]]"),
            CONFIG.replace("field =", "typo ="),
            CONFIG.replace('"subgroups"', '"s[0][name]"'),
            CONFIG.replace('"contains"', '""'),
            CONFIG.replace('name = "Synthetic group"', 'name = ""'),
            CONFIG + "\nunknown = true\n",
            "not valid TOML",
        ):
            with self.subTest(invalid=invalid):
                self.config.write_text(invalid)
                with (
                    patch.object(download, "resolve_cookies") as auth,
                    patch.object(refresh, "refresh_csv_files") as workflow,
                    self.assertRaises(SystemExit),
                ):
                    cli.main(["download", "--config", str(self.config)])
                auth.assert_not_called()
                workflow.assert_not_called()

    def test_custom_scope_reaches_both_cli_workflows(self):
        for command, operation in (
            ("download", "refresh_csv_files"),
            ("refresh", "refresh_analysis_lists"),
        ):
            with (
                self.subTest(command=command),
                patch.object(download, "resolve_cookies", return_value={}),
                patch.object(refresh, operation) as workflow,
            ):
                cli.main([command, "--config", str(self.config)])
                self.assertEqual(workflow.call_args.kwargs["scope"], self.scope)

    def test_custom_scope_is_used_for_every_table_and_published(self):
        csv_dir = self.root / "csv"
        debug_dir = self.root / "html"
        with patch.object(
            download.DataFetcher, "fetch_html", return_value=HTML
        ) as fetch:
            refresh.refresh_csv_files(
                self.tasks, csv_dir, debug_dir, scope=self.scope, debug=True
            )
        self.assertEqual(fetch.call_count, 4)
        for task, call in zip(self.tasks, fetch.call_args_list, strict=True):
            self.assertEqual(call.args[0], task.url)
            self.assertEqual(
                call.args[1],
                download.COMMON_PARAMS
                | self.scope.query_params()
                | {"s[0][name]": task.sort_by},
            )
        self.assertEqual(read_scope(csv_dir), self.scope)
        self.assertEqual(read_scope(debug_dir), self.scope)

        original = {p.name: p.read_bytes() for p in csv_dir.iterdir()}
        with (
            patch.object(download.DataFetcher, "fetch_html") as fetch,
            self.assertRaisesRegex(ValueError, "scope differs"),
        ):
            refresh.refresh_csv_files(self.tasks, csv_dir, debug_dir)
        fetch.assert_not_called()
        self.assertEqual(original, {p.name: p.read_bytes() for p in csv_dir.iterdir()})

    def test_scope_mismatch_in_snapshot_rejected_even_with_count_override(self):
        snapshot = self.root / "registry.json"
        GlanceRegistry(retrieval_scope=self.scope).store_json(snapshot)
        with (
            patch.object(download.DataFetcher, "fetch_html") as fetch,
            self.assertRaisesRegex(ValueError, "scope differs"),
        ):
            refresh.refresh_analysis_lists(
                self.root / "csv", self.root / "html", snapshot, force=True
            )
        fetch.assert_not_called()
        with self.assertRaisesRegex(ValueError, "scope differs"):
            refresh.compare_to_snapshot(GlanceRegistry(), snapshot)

    def test_scope_round_trips_and_legacy_snapshots_remain_readable(self):
        snapshot = self.root / "registry.json"
        GlanceRegistry(retrieval_scope=self.scope).store_json(snapshot)
        self.assertEqual(GlanceRegistry.from_json(snapshot).retrieval_scope, self.scope)
        GlanceRegistry().store_json(snapshot)
        self.assertNotIn("retrieval_scope", json.loads(snapshot.read_text()))
        self.assertIsNone(GlanceRegistry.from_json(snapshot).retrieval_scope)
        check_scope(load_scope(), None)
        with self.assertRaisesRegex(ValueError, "scope differs"):
            check_scope(self.scope, None)

    def test_values_are_deduplicated_and_scope_identity_ignores_order_and_label(self):
        scope = RetrievalScope(
            "Renamed", "subgroups", "contains", (904, 903, 902, 901, 901)
        )
        self.assertEqual(len(scope.values), 4)
        check_scope(scope, self.scope)

    def test_filter_field_and_operator_are_explicit_not_derived_from_hierarchy(self):
        # Synthetic query syntax tests transport, not live GLANCE support for a field.
        scope = RetrievalScope("Demo", "demo_group", "is", ("DEMO",))
        self.assertEqual(scope.query_params()["c[0][p]"], "demo_group")
        self.assertEqual(scope.query_params()["c[0][o]"], "is")

    def test_saved_html_with_different_scope_is_rejected(self):
        html_dir = self.root / "html"
        html_dir.mkdir()
        (html_dir / SCOPE_FILENAME).write_text(json.dumps(self.scope.metadata()))
        with self.assertRaisesRegex(ValueError, "scope differs"):
            refresh.refresh_csv_files(
                self.tasks, self.root / "csv", html_dir, use_local_html=True
            )

    def test_scope_metadata_rolls_back_with_csvs(self):
        csv_dir = self.root / "csv"
        with patch.object(download.DataFetcher, "fetch_html", return_value=HTML):
            refresh.refresh_csv_files(
                self.tasks, csv_dir, self.root / "html", scope=self.scope
            )
        original = {p.name: p.read_bytes() for p in csv_dir.iterdir()}
        replace = Path.replace

        def fail_metadata(source, destination):
            if source.name == SCOPE_FILENAME and source.parent.name != "previous":
                raise OSError("metadata publication failed")
            return replace(source, destination)

        with (
            patch.object(download.DataFetcher, "fetch_html", return_value=HTML),
            patch.object(Path, "replace", fail_metadata),
            self.assertRaisesRegex(OSError, "metadata publication"),
        ):
            refresh.refresh_csv_files(
                self.tasks, csv_dir, self.root / "html", scope=self.scope
            )
        self.assertEqual(original, {p.name: p.read_bytes() for p in csv_dir.iterdir()})
