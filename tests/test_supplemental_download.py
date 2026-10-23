# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline contracts for the reduced HTML supplement and its CLI."""

import csv
import html
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
from analysis_lister.downloaders.manifest import make_manifest
from analysis_lister.storage import SUPPLEMENT_MANIFEST


class SupplementTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "html"
        self.source.mkdir()
        self.destination = self.root / "supplements"
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
            "pubnotes": {
                "Temporary Reference Code": "PUB-DEMO-2099-01",
                "Reference Code": " ATL-PHYS-PUB-2099-001 ",
                "Creation Date": "2099-01-01",
                "Final URL": "https://example.test/publication",
                "Short Title": "Invented short title",
            },
        }
        (self.source / SUPPLEMENT_MANIFEST).write_text(
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

    def test_only_supplement_fields_survive_and_native_keys_are_preserved(self):
        self.run_download()
        expected = {
            "analyses": {"Reference Code", "Internal Note Editors"},
            "papers": {"Reference Code", "Figures", "Current Paper Draft"},
            "pubnotes": {"Temporary Reference Code", "Reference Code"},
        }
        for name, columns in expected.items():
            with (self.destination / f"{name}.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows, [{key: self.rows[name][key] for key in columns}])
        self.assertFalse((self.destination / "confnotes.csv").exists())
        manifest = json.loads((self.destination / SUPPLEMENT_MANIFEST).read_text())
        self.assertEqual(manifest["schema"], "glance-csv-supplements")
        self.assertEqual(set(manifest["tables"]), set(expected))

    def test_missing_field_or_native_identifier_aborts_entire_batch(self):
        for field, replacement in (
            ("Reference Code", None),
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

    def test_legacy_full_csv_directory_is_rejected_before_network_access(self):
        self.destination.mkdir()
        previous = self.destination / "analyses.csv"
        previous.write_text("Reference Code,Status\nANA-DEMO-2099-01,Active\n")
        (self.destination / SUPPLEMENT_MANIFEST).write_text(
            json.dumps(make_manifest(download.download_tasks()))
        )
        before = previous.read_bytes()
        with (
            patch.object(download.http.DataFetcher, "fetch_html") as network,
            self.assertRaisesRegex(ValueError, "different CSV format"),
        ):
            html_download.download_html_csvs(
                download.download_tasks(), self.destination, self.source
            )
        network.assert_not_called()
        self.assertEqual(previous.read_bytes(), before)

    def test_manifest_publication_failure_rolls_back_all_supplements(self):
        self.run_download()
        before = {p.name: p.read_bytes() for p in self.destination.iterdir()}
        self.rows["analyses"]["Internal Note Editors"] = "A different invented editor"
        self.write_html()
        replace = Path.replace

        def fail_manifest(source, target):
            if source.name == SUPPLEMENT_MANIFEST and source.parent.name != "previous":
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

    def test_html_and_registry_build_share_supplemental_default(self):
        parser = cli.parser()
        self.assertEqual(
            parser.parse_args(["download-html"]).csv_dir, Path("csv/supplemental")
        )
        self.assertEqual(
            parser.parse_args(["build-registry"]).csv_dir, Path("csv/supplemental")
        )


if __name__ == "__main__":
    unittest.main()
