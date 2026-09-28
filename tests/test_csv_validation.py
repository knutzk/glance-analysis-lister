"""Reject corrupt or ambiguous CSV records without changing GLANCE values."""

import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.download import HTMLParser
from analysis_lister.glance.glance_registry import GlanceRegistry


class CsvValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "analyses.csv"
        self.registry = GlanceRegistry.__new__(GlanceRegistry)

    def write_rows(self, rows):
        with self.path.open("w", newline="") as stream:
            csv.writer(stream).writerows(rows)

    def read_rows(self):
        return self.registry._read_csv_rows(
            self.path, ["Reference Code", "Status"], key="Reference Code", prefix="ANA-"
        )

    def test_preserves_status_whitespace_and_quoted_multiline_fields(self):
        status = " Phase 0 is  Active \nwith, comma"
        self.write_rows([["Reference Code", "Status"], ["ANA-TOPQ-2025-01", status]])
        self.assertEqual(self.read_rows()[0]["Status"], status)

    def test_missing_duplicate_or_empty_headers(self):
        for header in (
            ["Reference Code"],
            ["Reference Code", "Status", "Status"],
            ["Reference Code", "Status", ""],
        ):
            with self.subTest(header=header):
                self.write_rows([header, ["ANA-TOPQ-2025-01"] * len(header)])
                with self.assertRaisesRegex(
                    ValueError, "analyses.csv: invalid CSV headers"
                ):
                    self.read_rows()

    def test_short_and_long_rows(self):
        for row in (["ANA-TOPQ-2025-01"], ["ANA-TOPQ-2025-01", "status", "extra"]):
            with self.subTest(row=row):
                self.write_rows([["Reference Code", "Status"], row])
                with self.assertRaisesRegex(ValueError, "line 2: wrong number"):
                    self.read_rows()

    def test_duplicate_normalized_ids_are_rejected(self):
        self.write_rows(
            [
                ["Reference Code", "Status"],
                ["ANA-TOPQ-2025-01", "first"],
                ["TOPQ-2025-01", "second"],
            ]
        )
        with self.assertRaisesRegex(
            ValueError, "line 3: duplicate identifier.*first seen on line 2"
        ):
            self.read_rows()

    def test_empty_or_malformed_ids(self):
        for ref in ("", " ", "ANA-", "TOPQ-2025", "TOPQ-2025-01 trailing"):
            with self.subTest(ref=ref):
                self.write_rows([["Reference Code", "Status"], [ref, "status"]])
                with self.assertRaisesRegex(
                    ValueError, "line 2: invalid Reference Code"
                ):
                    self.read_rows()

    def test_unterminated_quoted_field(self):
        self.path.write_text('Reference Code,Status\nANA-TOPQ-2025-01,"unterminated')
        with self.assertRaisesRegex(ValueError, "invalid CSV"):
            self.read_rows()

    def test_html_bad_width_or_headers_do_not_overwrite_csv(self):
        for html in (
            "<table><tr><th>ID</th><th>Status</th></tr><tr><td>ID</td></tr></table>",
            "<table><tr><th>ID</th></tr><tr><td>ID</td><td>extra</td></tr></table>",
            "<table><tr><th>ID</th><th>ID</th></tr><tr><td>a</td><td>b</td></tr></table>",
        ):
            with self.subTest(html=html):
                self.path.write_text("previous")
                with self.assertRaises(ValueError):
                    HTMLParser.parse_to_csv(html, self.path)
                self.assertEqual(self.path.read_text(), "previous")

    def test_duplicate_unused_html_headers_are_allowed(self):
        HTMLParser.parse_to_csv(
            "<table><tr><th>ID</th><th>Unused</th><th>Unused</th></tr>"
            "<tr><td>one</td><td>a</td><td>b</td></tr></table>",
            self.path,
            column_filter=["ID"],
        )
        self.assertEqual(self.path.read_text(), '"ID"\n"one"\n')


if __name__ == "__main__":
    unittest.main()
