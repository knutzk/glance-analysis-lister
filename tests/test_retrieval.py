# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Synthetic retrieval scopes, query propagation and dataset boundaries."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister import cli
from analysis_lister.downloaders import (
    auth,
    csv_batch as html_download,
    html as download,
)
from analysis_lister.downloaders.scope import (
    SCOPE_FILENAME,
    RetrievalScope,
    check_scope,
    load_scope,
    read_scope,
)

HTML = "<span>Showing 1 to 1 of 1 results</span><table><tr><th>Reference Code</th></tr><tr><td>DEMO-2099-01</td></tr></table>"
CONFIG = """name = "Synthetic group"
[selection]
field = "subgroups"
operator = "contains"
values = [901, 902, 903, 904]
"""


class RetrievalTests(unittest.TestCase):
    def test_default_is_unfiltered_and_round_trips(self):
        scope = RetrievalScope.from_dict({"name": "ATLAS", "all": True})
        self.assertEqual(scope.query_params(), {})
        self.assertEqual(RetrievalScope.from_dict(scope.metadata()), scope)
        check_scope(scope, load_scope())
        for data in (
            {"name": "ATLAS"},
            {"name": "ATLAS", "all": False},
            {"name": "ATLAS", "all": "true"},
            {"name": "ATLAS", "all": True, "selection": {}},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                RetrievalScope.from_dict(data)

    def test_unfiltered_scope_cannot_also_contain_filters(self):
        with self.assertRaisesRegex(ValueError, "cannot include"):
            RetrievalScope("ATLAS", "subgroups", "contains", (1,), all=True)

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

    def test_explicit_topq_profile_preserves_historical_filters(self):
        params = load_scope(Path("analysis_lister/configs/topq.toml")).query_params()
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
                    patch.object(auth, "resolve_cookies") as credentials,
                    patch.object(html_download, "download_html_csvs") as workflow,
                    self.assertRaises(SystemExit),
                ):
                    cli.main(["download-html", "--config", str(self.config)])
                credentials.assert_not_called()
                workflow.assert_not_called()

    def test_custom_scope_reaches_html_cli_workflow(self):
        for command, operation in (("download-html", "download_html_csvs"),):
            with (
                self.subTest(command=command),
                patch.object(auth, "resolve_cookies", return_value={}),
                patch.object(html_download, operation) as workflow,
            ):
                cli.main([command, "--config", str(self.config)])
                self.assertEqual(workflow.call_args.kwargs["scope"], self.scope)

    def test_custom_scope_is_used_for_every_table_and_published(self):
        csv_dir = self.root / "csv"
        debug_dir = self.root / "html"
        with patch.object(
            download.http.DataFetcher, "fetch_html", return_value=HTML
        ) as fetch:
            html_download.download_html_csvs(
                self.tasks, csv_dir, debug_dir, scope=self.scope, debug=True
            )
        self.assertEqual(fetch.call_count, 4)
        for task, call in zip(self.tasks, fetch.call_args_list, strict=True):
            self.assertEqual(call.args[0], task.url)
            self.assertEqual(
                call.args[1],
                download.http.COMMON_PARAMS
                | self.scope.query_params()
                | {"s[0][name]": task.sort_by},
            )
        self.assertEqual(read_scope(csv_dir), self.scope)
        self.assertEqual(read_scope(debug_dir), self.scope)

        original = {p.name: p.read_bytes() for p in csv_dir.iterdir()}
        with (
            patch.object(download.http.DataFetcher, "fetch_html") as fetch,
            self.assertRaisesRegex(ValueError, "scope differs"),
        ):
            html_download.download_html_csvs(self.tasks, csv_dir, debug_dir)
        fetch.assert_not_called()
        self.assertEqual(original, {p.name: p.read_bytes() for p in csv_dir.iterdir()})

    def test_scope_round_trips_and_missing_scope_metadata_is_rejected(self):
        self.assertEqual(RetrievalScope.from_dict(self.scope.metadata()), self.scope)
        for scope in (
            load_scope(),
            self.scope,
            load_scope(Path("analysis_lister/configs/topq.toml")),
        ):
            with self.assertRaisesRegex(ValueError, "no retrieval scope metadata"):
                check_scope(scope, None)

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
            html_download.download_html_csvs(
                self.tasks, self.root / "csv", html_dir, use_local_html=True
            )

    def test_unknown_existing_csv_scope_rejected_before_fetch(self):
        csv_dir = self.root / "csv"
        csv_dir.mkdir()
        old = csv_dir / "analyses.csv"
        old.write_text("previous CSV")
        with (
            patch.object(download.http.DataFetcher, "fetch_html") as fetch,
            self.assertRaisesRegex(ValueError, "no retrieval scope metadata"),
        ):
            html_download.download_html_csvs(self.tasks, csv_dir, self.root / "html")
        fetch.assert_not_called()
        self.assertEqual(old.read_text(), "previous CSV")

    def test_saved_html_without_scope_metadata_is_not_assumed_unfiltered(self):
        html_dir = self.root / "html"
        html_dir.mkdir()
        for task in self.tasks:
            (html_dir / task.html_filename).write_text(HTML)
        destination = self.root / "csv"
        with self.assertRaisesRegex(ValueError, "no retrieval scope metadata"):
            html_download.download_html_csvs(
                self.tasks, destination, html_dir, use_local_html=True
            )
        self.assertFalse(destination.exists())

    def test_scope_metadata_rolls_back_with_csvs(self):
        csv_dir = self.root / "csv"
        with patch.object(download.http.DataFetcher, "fetch_html", return_value=HTML):
            html_download.download_html_csvs(
                self.tasks, csv_dir, self.root / "html", scope=self.scope
            )
        original = {p.name: p.read_bytes() for p in csv_dir.iterdir()}
        replace = Path.replace

        def fail_metadata(source, destination):
            if source.name == SCOPE_FILENAME and source.parent.name != "previous":
                raise OSError("metadata publication failed")
            return replace(source, destination)

        with (
            patch.object(download.http.DataFetcher, "fetch_html", return_value=HTML),
            patch.object(Path, "replace", fail_metadata),
            self.assertRaisesRegex(OSError, "metadata publication"),
        ):
            html_download.download_html_csvs(
                self.tasks, csv_dir, self.root / "html", scope=self.scope
            )
        self.assertEqual(original, {p.name: p.read_bytes() for p in csv_dir.iterdir()})
