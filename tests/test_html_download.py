# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline contracts for the standalone HTML download and its CLI."""

import csv
import html
import io
import json
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister import cli
from analysis_lister.downloaders import (
    auth,
    csv_batch as html_download,
    html as download,
)
from analysis_lister.downloaders.manifest import HTML_MANIFEST, make_manifest


class HtmlDownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "html"
        self.source.mkdir()
        self.destination = self.root / "exports"
        self.rows = {
            "analyses": {
                "Reference Code": "ANA-DEMO-2099-01",
                "Full Title": " A synthetic full title ",
                "Internal Note Editors": "Invented Editor",
                "Status": " Phase 0 is  Active ",
                "Keywords": "Invented keyword",
            },
            "papers": {
                "Reference Code": "DEMO-2099-01",
                "Figures": "https://example.test/figures",
                "Current Paper Draft": "Invented draft",
                "ArXiv Reference URLs": "https://example.test/preprint",
                "Contact Editors": "Invented Editor",
            },
            "confnotes": {
                "Temporary Reference Code": "CONF-DEMO-2099-01",
                "Reference Code": "ATLAS-CONF-2099-001",
                "Status": " Phase 1 Finished ",
            },
            "pubnotes": {
                "Temporary Reference Code": "PUB-DEMO-2099-01",
                "Reference Code": " ATL-PHYS-PUB-2099-001 ",
                "Creation Date": "2099-01-01",
                "Final URL": "https://example.test/publication",
                "Short Title": "Invented short title",
            },
        }
        (self.source / HTML_MANIFEST).write_text(
            json.dumps(make_manifest(download.download_tasks()))
        )
        self.write_html()

    def write_html(self):
        for name, row in self.rows.items():
            table = (
                "<span>Showing 1 to 1 of 1 results</span><table><tr>"
                + "".join(f"<th>{html.escape(key)}</th>" for key in row)
                + "</tr><tr>"
                + "".join(f"<td>{html.escape(value)}</td>" for value in row.values())
                + "</tr></table>"
            )
            (self.source / f"{name}.html").write_text(table)

    def run_download(self):
        with (
            patch.object(auth.CookieManager, "load_cookies") as cookies,
            patch.object(download.http.DataFetcher, "fetch_html") as network,
        ):
            cli.main(
                [
                    "download-html",
                    "--from-html",
                    str(self.source),
                    "--csv-dir",
                    str(self.destination),
                ]
            )
        cookies.assert_not_called()
        network.assert_not_called()

    def test_conflicting_options_fail_before_authentication(self):
        for options in (
            ["--from-html", str(self.source), "--save-html", str(self.source)],
            ["--from-html", str(self.source), "--login"],
            ["--save-html", str(self.destination), "--csv-dir", str(self.destination)],
        ):
            with (
                self.subTest(options=options),
                patch.object(auth, "resolve_cookies") as cookies,
                patch("sys.stderr", io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                cli.main(["download-html", *options])
            self.assertEqual(error.exception.code, 2)
            cookies.assert_not_called()

    def test_all_columns_and_all_resources_are_preserved(self):
        self.run_download()
        for name, row in self.rows.items():
            with (self.destination / f"{name}.csv").open(newline="") as stream:
                self.assertEqual(list(csv.DictReader(stream)), [row])
        manifest = json.loads((self.destination / HTML_MANIFEST).read_text())
        self.assertEqual(manifest["schema"], "glance-html-csv")
        self.assertEqual(set(manifest["tables"]), set(self.rows))

    def test_missing_field_or_native_identifier_aborts_entire_batch(self):
        for field, replacement in (
            ("Temporary Reference Code", None),
            ("Temporary Reference Code", "invalid"),
        ):
            with self.subTest(field=field):
                original = self.rows["pubnotes"].copy()
                if replacement is None:
                    self.rows["pubnotes"].pop(field)
                else:
                    self.rows["pubnotes"][field] = replacement
                self.write_html()
                with self.assertRaises(ValueError):
                    html_download.download_html_csvs(
                        download.download_tasks(),
                        self.destination,
                        self.source,
                        use_local_html=True,
                    )
                self.assertEqual(list(self.destination.iterdir()), [])
                self.rows["pubnotes"] = original

    def test_unrecognised_destination_manifest_is_rejected_before_network_access(self):
        self.destination.mkdir()
        previous = self.destination / "analyses.csv"
        previous.write_text("Reference Code,Status\nANA-DEMO-2099-01,Active\n")
        (self.destination / HTML_MANIFEST).write_text(json.dumps({"schema": "other"}))
        before = previous.read_bytes()
        with (
            patch.object(download.http.DataFetcher, "fetch_html") as network,
            self.assertRaisesRegex(ValueError, "manifest"),
        ):
            html_download.download_html_csvs(
                download.download_tasks(), self.destination, self.source
            )
        network.assert_not_called()
        self.assertEqual(previous.read_bytes(), before)

    def test_manifest_publication_failure_rolls_back_all_exports(self):
        self.run_download()
        before = {p.name: p.read_bytes() for p in self.destination.iterdir()}
        self.rows["analyses"]["Internal Note Editors"] = "A different invented editor"
        self.write_html()
        replace = Path.replace

        def fail_manifest(source, target):
            if source.name == HTML_MANIFEST and source.parent.name != "previous":
                raise OSError("manifest publication failed")
            return replace(source, target)

        with patch.object(Path, "replace", fail_manifest), self.assertRaises(OSError):
            html_download.download_html_csvs(
                download.download_tasks(),
                self.destination,
                self.source,
                use_local_html=True,
            )
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.destination.iterdir()}
        )

    def test_default_html_output_is_in_callers_working_directory(self):
        with TemporaryDirectory() as workspace, chdir(workspace):
            Path("unrelated.csv").write_text("preserve this file\n")
            cli.main(["download-html", "--from-html", str(self.source)])
            for task in download.download_tasks():
                self.assertTrue(Path(task.csv_filename).is_file())
            self.assertTrue(Path(HTML_MANIFEST).is_file())
            self.assertEqual(Path("unrelated.csv").read_text(), "preserve this file\n")
            self.assertFalse(Path("csv").exists())
            self.assertFalse(Path("json").exists())
            self.assertFalse(Path(".html-download-in-progress").exists())

    def test_only_html_download_uses_csv_directory(self):
        parser = cli.parser()
        self.assertEqual(parser.parse_args(["download-html"]).csv_dir, Path("."))
        self.assertFalse(hasattr(parser.parse_args(["build-registry"]), "csv_dir"))


if __name__ == "__main__":
    unittest.main()
