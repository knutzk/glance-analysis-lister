# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Synthetic API pagination and publication failure regressions."""

import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from analysis_lister.downloaders.api import (
    RESOURCES,
    SORT_FIELDS,
    collect_registry,
    download_registry,
    publish_registry,
)


def client_for(count=3):
    client = SimpleNamespace()
    for name in RESOURCES:
        field = (
            "temporaryReferenceCode"
            if name in {"confnotes", "pubnotes"}
            else "referenceCode"
        )
        models = []
        for number in range(count):
            model = Mock()
            model.model_dump.return_value = {
                field: f"DEMO-2099-{number:02}",
                "metadata": {"nested": ["invented"]},
            }
            models.append(model)

        def search(*, offset, limit, sort_by=None, sort_desc=False, records=models):
            return SimpleNamespace(
                number_of_results=len(records), results=records[offset : offset + limit]
            )

        setattr(client, name, SimpleNamespace(search=Mock(side_effect=search)))
    return client


class ApiTests(unittest.TestCase):
    def test_browser_login_and_saved_login_both_download_without_cache(self):
        for login in (False, True):
            with self.subTest(login=login), TemporaryDirectory() as directory:
                path = Path(directory) / "registry.json"
                with (
                    patch("stare.Glance") as glance,
                    patch("stare.auth.TokenManager") as manager,
                    patch("stare.settings.StareSettings") as settings,
                ):
                    settings.return_value.base_url = "https://example.test/api"
                    glance.return_value.__enter__.return_value = client_for()
                    counts = download_registry(path, login=login)
                    self.assertEqual(counts, dict.fromkeys(RESOURCES, 3))
                    settings.assert_called_once_with(cache_enabled=False)
                    self.assertEqual(manager.return_value.login.call_count, int(login))
                    glance.assert_called_once_with(
                        settings=settings.return_value,
                        token_manager=manager.return_value,
                    )
                    self.assertEqual(
                        json.loads(path.read_text())["source"]["base_url"],
                        "https://example.test/api",
                    )

    def test_download_failure_preserves_file_and_hides_response_details(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text("previous snapshot")
            with (
                patch("stare.auth.TokenManager", side_effect=RuntimeError("secret")),
                self.assertRaises(ValueError) as caught,
            ):
                download_registry(path)
            self.assertNotIn("secret", str(caught.exception))
            self.assertIn("--login", str(caught.exception))
            self.assertEqual(path.read_text(), "previous snapshot")

    def test_collects_all_pages_and_preserves_nested_records(self):
        client = client_for()
        result = collect_registry(client, page_size=2)
        self.assertEqual(result["counts"], dict.fromkeys(RESOURCES, 3))
        self.assertEqual(result["analyses"][0]["metadata"], {"nested": ["invented"]})
        self.assertEqual(client.analyses.search.call_count, 2)
        self.assertEqual(result["source"]["sort_fields"], SORT_FIELDS)
        self.assertFalse(result["source"]["sort_descending"])
        for resource in RESOURCES:
            self.assertEqual(
                getattr(client, resource).search.call_args_list,
                [
                    call(
                        offset=0,
                        limit=2,
                        sort_by=SORT_FIELDS[resource],
                        sort_desc=False,
                    ),
                    call(
                        offset=2,
                        limit=2,
                        sort_by=SORT_FIELDS[resource],
                        sort_desc=False,
                    ),
                ],
            )

    def test_larger_page_sizes_are_requested_and_recorded(self):
        for size in (250, 500):
            with self.subTest(page_size=size):
                client = client_for()
                result = collect_registry(client, page_size=size)
                self.assertEqual(result["source"]["page_size"], size)
                for resource in RESOURCES:
                    getattr(client, resource).search.assert_called_once_with(
                        offset=0,
                        limit=size,
                        sort_by=SORT_FIELDS[resource],
                        sort_desc=False,
                    )
        with patch("stare.Glance") as glance:
            for invalid in (0, -1, True, 1.5, "250"):
                with (
                    self.subTest(invalid=invalid),
                    self.assertRaisesRegex(ValueError, "positive integer"),
                ):
                    download_registry("unused.json", page_size=invalid)
            glance.assert_not_called()

    def test_rejects_duplicate_page(self):
        client = client_for()
        page = client.analyses.search(offset=0, limit=2)
        client.analyses.search.side_effect = None
        client.analyses.search.return_value = page
        with self.assertRaises(ValueError):
            collect_registry(client, page_size=2)

    def test_rejects_changed_total_and_truncated_response(self):
        for total, batch in ((4, [Mock()]), (3, [])):
            with self.subTest(total=total), self.assertRaises(ValueError):
                client = client_for()
                first = client.analyses.search(offset=0, limit=2)
                client.analyses.search.side_effect = [
                    first,
                    SimpleNamespace(number_of_results=total, results=batch),
                ]
                collect_registry(client, page_size=2)

    def test_count_guard_and_format_guard_preserve_destination(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "registry.json"
            old = collect_registry(client_for(3))
            publish_registry(old, path)
            before = path.read_bytes()
            candidate = collect_registry(client_for(1))
            with self.assertRaisesRegex(ValueError, "20%"):
                publish_registry(candidate, path)
            self.assertEqual(before, path.read_bytes())
            invalid = copy.deepcopy(candidate)
            invalid["counts"]["papers"] = 99
            with self.assertRaises(ValueError):
                publish_registry(invalid, path, allow_count_drop=True)
            self.assertEqual(before, path.read_bytes())
            publish_registry(candidate, path, allow_count_drop=True)
            self.assertEqual(json.loads(path.read_text())["counts"]["papers"], 1)
            path.write_text('{"entries": {}}')
            with self.assertRaises(ValueError):
                publish_registry(candidate, path, allow_count_drop=True)


if __name__ == "__main__":
    unittest.main()
