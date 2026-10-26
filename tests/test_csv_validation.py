# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Reject corrupt or ambiguous CSV records without changing GLANCE values."""

import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.downloaders.csv_io import read_csv_rows
from analysis_lister.downloaders.html import HTMLParser
from analysis_lister.downloaders.tables import (
    parse_html_table,
    table_to_rows,
    validate_table_completeness,
)


class CsvValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "analyses.csv"

    def write_rows(self, rows):
        with self.path.open("w", newline="") as stream:
            csv.writer(stream).writerows(rows)

    def read_rows(self):
        return read_csv_rows(
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

    def test_invalid_table_is_saved_for_diagnostics_without_replacing_csv(self):
        self.path.write_text("previous CSV")
        diagnostic = self.path.parent / "debug" / "analyses.html"
        html = "<table><tr><th>Renamed</th></tr><tr><td>entry</td></tr></table>"
        with self.assertRaisesRegex(ValueError, "Missing columns"):
            HTMLParser.parse_to_csv(
                html, self.path, diagnostic, column_filter=["Reference Code"]
            )
        self.assertEqual(self.path.read_text(), "previous CSV")
        self.assertEqual(diagnostic.read_text(), html + "\n")

    def test_duplicate_unused_html_headers_are_allowed(self):
        HTMLParser.parse_to_csv(
            "<span>Showing 1 to 1 of 1 results</span>"
            "<table><tr><th>ID</th><th>Unused</th><th>Unused</th></tr>"
            "<tr><td>one</td><td>a</td><td>b</td></tr></table>",
            self.path,
            column_filter=["ID"],
        )
        self.assertEqual(self.path.read_text(), '"ID"\n"one"\n')


class HtmlTableParsingTests(unittest.TestCase):
    def test_reported_totals_accept_complete_responses_and_number_separators(self):
        for total in ("1234", "1,234", "1 234", "1\u00a0234", "1\u202f234"):
            with self.subTest(total=total):
                table = parse_html_table(
                    f"<span>Showing 1 to {total} of {total} results</span>"
                    "<table><tr><th>ID</th></tr><tr><td>synthetic</td></tr></table>",
                    source="synthetic response",
                )
                validate_table_completeness(table, 1234, source="synthetic response")

    def test_reported_totals_reject_missing_conflicting_and_partial_results(self):
        for summary in (
            "",
            "<span>Showing 1 to 2 of 5 results</span>",
            "<span>Showing 3 to 5 of 5 results</span>",
            "<span>Showing 1 to 5 of 5 results</span>",
            "<span>Showing 1 to 1 of 1 results</span>"
            "<span>Showing 1 to 2 of 2 results</span>",
            "<script>Showing 1 to 1 of 1 results</script>",
        ):
            with self.subTest(summary=summary):
                table = parse_html_table(
                    summary
                    + "<table><tr><th>ID</th></tr><tr><td>synthetic</td></tr></table>",
                    source="synthetic response",
                )
                with self.assertRaises(ValueError):
                    validate_table_completeness(table, 1, source="synthetic response")

    def test_record_text_cannot_supply_a_missing_counter(self):
        table = parse_html_table(
            "<table><tr><th>Comment</th></tr>"
            "<tr><td>Showing 1 to 1 of 1 results</td></tr></table>",
            source="synthetic response",
        )
        with self.assertRaisesRegex(ValueError, "completeness cannot be verified"):
            validate_table_completeness(table, 1, source="synthetic response")

    def test_repaired_rows_preserve_cell_whitespace_and_source_column_order(self):
        table = parse_html_table(
            "<table><tr><th> Status </th><th>ID</th><th>Unused</th></tr>"
            "<tr><td> Phase 0 is  Active <td>first<td>ignored</td></tr></table>",
            source="synthetic table",
        )
        self.assertEqual(
            table_to_rows(
                table, source="synthetic table", column_filter=["ID", "Status"]
            ),
            [["Status", "ID"], [" Phase 0 is  Active ", "first"]],
        )

    def test_parser_diagnostics_identify_source_and_bad_row(self):
        with self.assertRaisesRegex(ValueError, "No table found for synthetic source"):
            parse_html_table("<html>login</html>", source="synthetic source")
        table = parse_html_table(
            "<table><tr><th>ID</th><th>Status</th></tr>"
            "<tr><td>only one cell</td></tr></table>",
            source="synthetic source",
        )
        with self.assertRaisesRegex(
            ValueError, "synthetic source: table row 2: expected 2 cells, found 1"
        ):
            table_to_rows(table, source="synthetic source")


if __name__ == "__main__":
    unittest.main()
