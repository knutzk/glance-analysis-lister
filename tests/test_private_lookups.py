"""Private topic lookups remain local and cannot execute Python code."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister import cli
from analysis_lister.lookup_dicts.overrides import local_lookups
from analysis_lister.lookup_dicts.short_titles import ShortTitles
from analysis_lister.lookup_dicts.validation import TABLES


class PrivateLookupTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for filename, table in TABLES.items():
            (self.directory / filename).write_text(f"{table} = {{}}\n")
        (self.directory / "short_titles.py").write_text(
            'ShortTitles = {"TOPQ-2099-01": "Synthetic title"}\n'
        )

    def test_public_defaults_contain_no_analysis_topics(self):
        self.assertEqual(ShortTitles, {})

    def test_imported_dictionary_sees_local_values_and_restores_after_failure(self):
        original = ShortTitles.copy()
        with (
            self.assertRaisesRegex(RuntimeError, "render failed"),
            local_lookups(self.directory),
        ):
            self.assertEqual(ShortTitles, {"TOPQ-2099-01": "Synthetic title"})
            raise RuntimeError("render failed")
        self.assertEqual(ShortTitles, original)

    def test_duplicate_keys_fail_before_changing_defaults(self):
        (self.directory / "short_titles.py").write_text(
            'ShortTitles = {"TOPQ-2099-01": "one", "TOPQ-2099-01": "two"}'
        )
        with (
            self.assertRaisesRegex(ValueError, "duplicate key"),
            local_lookups(self.directory),
        ):
            self.fail("Invalid dictionary must not be applied")
        self.assertEqual(ShortTitles, {})

    def test_private_source_is_never_executed(self):
        marker = self.directory / "executed"
        (self.directory / "short_titles.py").write_text(
            f'ShortTitles = {{}}\nopen({str(marker)!r}, "w").close()\n'
        )
        with (
            self.assertRaisesRegex(ValueError, "unsupported statement"),
            local_lookups(self.directory),
        ):
            self.fail("Executable source must be rejected")
        self.assertFalse(marker.exists())

    def test_cli_supplies_private_titles_only_during_render(self):
        def render(*args):
            self.assertEqual(ShortTitles["TOPQ-2099-01"], "Synthetic title")

        with patch("analysis_lister.render.render_pages", side_effect=render) as call:
            cli.main(["render", "--lookup-dir", str(self.directory)])
        call.assert_called_once()
        self.assertEqual(ShortTitles, {})
