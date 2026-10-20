# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Source-level checks for maintained dictionaries, including overwritten keys."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.lookup_dicts.validation import TABLES, validate_lookups


class LookupValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for filename, table in TABLES.items():
            (self.directory / filename).write_text(f"{table} = {{}}\n")

    def write(self, filename, content):
        (self.directory / filename).write_text(content)

    def test_repository_tables_are_valid(self):
        validate_lookups()

    def test_optional_clone_dictionary_rejects_cycles_and_invalid_references(self):
        self.write(
            "clones.py",
            """Clones = {
# Source: synthetic relationship
"DEMO-2099-01": "DEMO-2099-02",
# Source: synthetic conflicting relationship
"DEMO-2099-02": "DEMO-2099-01",
}""",
        )
        with self.assertRaisesRegex(ValueError, "clone mapping cycle"):
            validate_lookups(self.directory)
        self.write(
            "clones.py",
            """Clones = {
# Source: synthetic invalid relationship
"DEMO-2099-01": "invalid",
}""",
        )
        with self.assertRaisesRegex(ValueError, "expected an analysis reference code"):
            validate_lookups(self.directory)

    def test_optional_clone_dictionary_applies_without_execution(self):
        from analysis_lister.lookup_dicts.clones import Clones
        from analysis_lister.lookup_dicts.overrides import local_lookups

        original = Clones.copy()
        self.write(
            "clones.py",
            """Clones = {
# Source: synthetic relationship
"DEMO-2099-02": "DEMO-2099-01",
}""",
        )
        with local_lookups(self.directory):
            self.assertEqual(Clones, {"DEMO-2099-02": "DEMO-2099-01"})
        self.assertEqual(Clones, original)

    def test_historical_records_and_unicode_titles_are_valid(self):
        self.write(
            "short_titles.py", 'ShortTitles = {"TOPQ-1999-01": "ttγ – historical"}'
        )
        self.write(
            "doi_order.py",
            'DoiOrder: dict[str, list[str]] = {\n# Source: historical publisher record checked by maintainer\n"TOPQ-1999-01": ["10.1007/JHEP07(2023)203", "10.1007/JHEP05(2025)159"]}',
        )
        validate_lookups(self.directory)

    def test_duplicate_literal_keys_report_both_lines(self):
        self.write(
            "short_titles.py",
            'ShortTitles = {\n"TOPQ-2025-01": "first",\n"TOPQ-2025-01": "second",\n}',
        )
        with self.assertRaisesRegex(
            ValueError, r"short_titles.py:3: duplicate key.*first defined on line 2"
        ):
            validate_lookups(self.directory)

    def test_factual_overrides_require_their_own_provenance_comment(self):
        for filename, table, value in (
            ("known_duplicates.py", "KnownDuplicates", '"TOPQ-2025-02"'),
            ("clones.py", "Clones", '"TOPQ-2025-02"'),
            ("doi_order.py", "DoiOrder", '["10.1007/example"]'),
        ):
            with self.subTest(table=table):
                self.write(filename, f'{table} = {{\n"TOPQ-2025-01": {value}\n}}')
                with self.assertRaisesRegex(ValueError, "add a # Reason: or # Source:"):
                    validate_lookups(self.directory)
                self.write(
                    filename,
                    f'{table} = {{\n# Reason: checked against the source record\n"TOPQ-2025-01": {value}\n}}',
                )
                validate_lookups(self.directory)

    def test_comment_on_previous_entry_does_not_document_next_entry(self):
        self.write(
            "known_duplicates.py",
            """KnownDuplicates = {
    # Reason: record comparison
    "TOPQ-2025-01": "TOPQ-2025-03",
    "TOPQ-2025-02": "TOPQ-2025-03",
}""",
        )
        with self.assertRaisesRegex(ValueError, "TOPQ-2025-02: add a # Reason:"):
            validate_lookups(self.directory)

    def test_errors_are_collected_across_files(self):
        self.write(
            "short_titles.py", 'ShortTitles = {"TOPQ-2025-01": "  ", "bad ID": "title"}'
        )
        self.write(
            "journal_refs.py",
            'JournalRefs = {"https://doi.org/10.1007/example": "citation", "10.1007/example": 42}',
        )
        with self.assertRaises(ValueError) as error:
            validate_lookups(self.directory)
        message = str(error.exception)
        for fragment in (
            "short_titles.py",
            "journal_refs.py",
            "nonempty string",
            "invalid ShortTitles key",
            "invalid JournalRefs key",
        ):
            self.assertIn(fragment, message)

    def test_doi_orders_reject_invalid_types_empty_lists_and_duplicates(self):
        for value in (
            "[]",
            '"10.1007/example"',
            '["bad DOI"]',
            '["10.1007/example", "10.1007/example"]',
        ):
            with self.subTest(value=value):
                self.write("doi_order.py", 'DoiOrder = {"TOPQ-2025-01": ' + value + "}")
                with self.assertRaisesRegex(ValueError, "doi_order.py:1"):
                    validate_lookups(self.directory)

    def test_duplicate_mapping_cycles_are_rejected(self):
        for entries in (
            '"TOPQ-2025-01": "TOPQ-2025-01"',
            '"TOPQ-2025-01": "TOPQ-2025-02", "TOPQ-2025-02": "TOPQ-2025-01"',
        ):
            with self.subTest(entries=entries):
                self.write("known_duplicates.py", "KnownDuplicates = {" + entries + "}")
                with self.assertRaisesRegex(ValueError, "duplicate mapping cycle"):
                    validate_lookups(self.directory)

    def test_missing_syntax_invalid_or_dynamic_definitions_are_rejected(self):
        for source in (
            "ShortTitles = {",
            "WrongName = {}",
            "ShortTitles = dict()",
            "ShortTitles = {}\nShortTitles = {}",
            'ShortTitles = {}\nraise RuntimeError("must not execute")',
        ):
            with self.subTest(source=source):
                self.write("short_titles.py", source)
                with self.assertRaisesRegex(ValueError, "short_titles.py"):
                    validate_lookups(self.directory)
        (self.directory / "short_titles.py").unlink()
        with self.assertRaisesRegex(ValueError, "short_titles.py"):
            validate_lookups(self.directory)

    def test_registry_loaders_validate_before_reading_input(self):
        with patch(
            "analysis_lister.glance.glance_registry.validate_lookups",
            side_effect=ValueError("invalid lookups"),
        ):
            with self.assertRaisesRegex(ValueError, "invalid lookups"):
                GlanceRegistry.from_csv(csv_dir=self.directory / "missing")
            with self.assertRaisesRegex(ValueError, "invalid lookups"):
                GlanceRegistry.from_json(self.directory / "missing.json")


if __name__ == "__main__":
    unittest.main()
