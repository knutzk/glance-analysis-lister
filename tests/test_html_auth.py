# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline browser/cookie lifecycle and optional dependency boundaries."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis_lister.downloaders.auth import CookieManager, resolve_cookies


class HtmlAuthTests(unittest.TestCase):
    def test_cookies_are_private_and_loaded_without_starting_browser(self):
        cookies = [{"name": "session", "value": "synthetic-secret"}]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested/cookies.json"
            CookieManager.save_cookies(cookies, path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.chmod(0o644)
            CookieManager.save_cookies(cookies, path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with patch.object(CookieManager, "generate_cookies") as browser:
                self.assertEqual(resolve_cookies(path), {"session": "synthetic-secret"})
            browser.assert_not_called()
            self.assertEqual(json.loads(path.read_text()), cookies)
            with self.assertRaisesRegex(ValueError, "--login"):
                resolve_cookies(Path(directory) / "missing.json")

    def test_manual_browser_login_always_quits_even_if_saving_fails(self):
        for fail in (False, True):
            with (
                self.subTest(fail=fail),
                patch("selenium.webdriver.Chrome") as chrome,
                patch("selenium.webdriver.chrome.service.Service"),
                patch("builtins.input"),
                patch.object(CookieManager, "save_cookies") as save,
            ):
                chrome.return_value.get_cookies.return_value = []
                if fail:
                    save.side_effect = OSError("disk full")
                    with self.assertRaises(OSError):
                        CookieManager.generate_cookies(Path("unused.json"))
                else:
                    self.assertEqual(
                        CookieManager.generate_cookies(Path("unused.json")), []
                    )
                chrome.return_value.quit.assert_called_once()

    def test_cli_help_and_api_import_work_without_html_dependencies(self):
        code = """
import importlib.abc
import sys
class NoHtmlDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'bs4', 'selenium'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, NoHtmlDependencies())
from analysis_lister.downloaders import api
from analysis_lister.cli import main
for args in (['--help'], ['download-html', '--help'], ['download-api', '--help']):
    try:
        main(args)
    except SystemExit as error:
        assert error.code == 0
try:
    main(['download-html', '--login'])
except SystemExit as error:
    assert error.code == 1
else:
    raise AssertionError('Missing dependencies must fail before login')
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("glance-analysis-lister[html]", result.stderr)
