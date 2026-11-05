# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Consumer-facing generated names and record identities, independent of layout."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup

from analysis_lister.views.build import render_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = {
    "ongoing.md": "analysis-demo-ana-demo-2099-01",
    "papers.md": "publication-papers-demo-demo-2099-01",
    "confnotes.md": "confnote-demo-conf-demo-2099-01",
    "pubnotes.md": "pubnote-demo-pub-demo-2099-01",
}


class GeneratedContractTests(unittest.TestCase):
    def test_filenames_and_record_fragments_survive_display_changes(self):
        data = json.loads((ROOT / "examples/synthetic_registry.json").read_text())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "synthetic.json"
            output = root / "pages"
            for changed in (False, True):
                if changed:
                    for resource in ("analyses", "papers", "confnotes", "pubnotes"):
                        data[resource][0]["shortTitle"] = "A different invented title"
                        data[resource].reverse()
                    for resource, label in (
                        ("confnotes", "ATLAS-CONF-2099-099"),
                        ("pubnotes", "ATL-PHYS-PUB-2099-099"),
                    ):
                        data[resource][-1]["gal_finalReferenceCode"] = label
                        data[resource][-1]["finalReferenceCode"] = label
                source.write_text(json.dumps(data))
                render_group(
                    source,
                    output,
                    GroupProfile(
                        "DEMO",
                        title="Changed heading" if changed else "Original heading",
                        publication_policy=PublicationPolicy(
                            groups=("DEMO",),
                            title="Changed publications"
                            if changed
                            else "Original publications",
                        ),
                    ),
                )
                expected_files = {
                    *FRAGMENTS,
                    "view-report.json",
                    *(
                        f"assets/gal-{component}.{extension}"
                        for component in ("common", "ongoing", "papers", "notes")
                        for extension in ("css", "js")
                    ),
                }
                actual_files = {
                    path.relative_to(output).as_posix()
                    for path in output.rglob("*")
                    if path.is_file()
                }
                self.assertLessEqual(expected_files, actual_files)
                for page, fragment in FRAGMENTS.items():
                    with self.subTest(changed=changed, page=page):
                        html = BeautifulSoup((output / page).read_text(), "html.parser")
                        self.assertEqual(len(html.find_all(id=fragment)), 1)
                        if page == "ongoing.md":
                            self.assertIsNotNone(html.find("a", href="#" + fragment))


if __name__ == "__main__":
    unittest.main()
