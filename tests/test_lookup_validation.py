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
from analysis_lister.lookup_validation import TABLES, validate_lookups


class LookupValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for filename, table in TABLES.items():
            (self.directory / filename).write_text(f"{table} = {{}}\n")

    def write(self, filename, content):
        (self.directory / filename).write_text(content)

    def test_ignore_dictionary_requires_reasons_and_valid_identifiers(self):
        for key, reason in (
            ("invalid", "Synthetic reason"),
            ("DEMO-2099-01", ""),
            ("DEMO-2099-01", 1),
        ):
            with self.subTest(key=key, reason=reason):
                self.write(
                    "ignored_analyses.py",
                    f"IgnoredAnalyses = {{\n# Reason: synthetic exception\n{key!r}: {reason!r},\n}}\n",
                )
                with self.assertRaisesRegex(ValueError, "ignored_analyses.py"):
                    validate_lookups(self.directory)

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

    def test_historical_records_are_valid(self):
        self.write(
            "clones.py",
            'Clones = {\n# Source: historical comparison\n"DEMO-1999-01": "DEMO-1999-02"}',
        )
        validate_lookups(self.directory)

    def test_duplicate_literal_keys_report_both_lines(self):
        self.write(
            "clones.py",
            'Clones = {\n"TOPQ-2025-01": "first",\n"TOPQ-2025-01": "second",\n}',
        )
        with self.assertRaisesRegex(
            ValueError, r"clones.py:3: duplicate key.*first defined on line 2"
        ):
            validate_lookups(self.directory)

    def test_factual_overrides_require_their_own_provenance_comment(self):
        for filename, table, value in (("clones.py", "Clones", '"TOPQ-2025-02"'),):
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
            "clones.py",
            """Clones = {
    # Reason: record comparison
    "TOPQ-2025-01": "TOPQ-2025-03",
    "TOPQ-2025-02": "TOPQ-2025-03",
}""",
        )
        with self.assertRaisesRegex(ValueError, "TOPQ-2025-02: add a # Reason:"):
            validate_lookups(self.directory)

    def test_duplicate_mapping_cycles_are_rejected(self):
        for entries in (
            '"TOPQ-2025-01": "TOPQ-2025-01"',
            '"TOPQ-2025-01": "TOPQ-2025-02", "TOPQ-2025-02": "TOPQ-2025-01"',
        ):
            with self.subTest(entries=entries):
                self.write("clones.py", "Clones = {" + entries + "}")
                with self.assertRaisesRegex(ValueError, "clone mapping cycle"):
                    validate_lookups(self.directory)

    def test_missing_syntax_invalid_or_dynamic_definitions_are_rejected(self):
        for source in (
            "Clones = {",
            "WrongName = {}",
            "Clones = dict()",
            "Clones = {}\nClones = {}",
            'Clones = {}\nraise RuntimeError("must not execute")',
        ):
            with self.subTest(source=source):
                self.write("clones.py", source)
                with self.assertRaisesRegex(ValueError, "clones.py"):
                    validate_lookups(self.directory)
        (self.directory / "clones.py").unlink()
        with self.assertRaisesRegex(ValueError, "clones.py"):
            validate_lookups(self.directory)

    def test_registry_loaders_validate_before_reading_input(self):
        with (
            patch(
                "analysis_lister.glance.glance_registry.validate_lookups",
                side_effect=ValueError("invalid lookups"),
            ),
            self.assertRaisesRegex(ValueError, "invalid lookups"),
        ):
            GlanceRegistry.from_json(self.directory / "missing.json")


if __name__ == "__main__":
    unittest.main()
