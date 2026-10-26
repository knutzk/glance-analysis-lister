# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Cross-process reproducibility, input identities and unchanged-file publication."""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from view_fixtures import analysis, publication, snapshot

from analysis_lister.provenance import generator_fingerprint, json_fingerprint
from analysis_lister.views.build import render_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

ROOT = Path(__file__).resolve().parents[1]


def contents(directory):
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def fixture():
    active = analysis(1)
    active["gal_groups"]["subgroups"] = ["DEMO-Beta", "DEMO-Alpha"]
    uncertain = analysis(2, status="Phase 0 Finished")
    paper = publication(1)
    paper["gal_groups"]["subgroups"] = ["DEMO-Alpha", "DEMO-Beta"]
    note = publication(2, resource="confnotes", status="Phase 1 Finished")
    pub = publication(3, resource="pubnotes", status="Phase 1 Finished")
    return snapshot(
        active, uncertain, papers=(paper,), confnotes=(note,), pubnotes=(pub,)
    )


class RenderReproducibilityTests(unittest.TestCase):
    def test_processes_hash_seeds_timezones_and_equivalent_configs_match(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = None
            for index, (seed, zone) in enumerate(
                (("1", "UTC"), ("17", "Pacific/Honolulu"), ("123", "Europe/Zurich"))
            ):
                work = root / str(index)
                work.mkdir()
                source, config, output = (
                    work / "registry.json",
                    work / "policy.toml",
                    work / "pages",
                )
                # Reuse exactly the same bytes, including snapshot metadata.
                if index == 0:
                    raw = json.dumps(fixture(), ensure_ascii=False).encode()
                source.write_bytes(raw)
                config.write_text(
                    '[groups.DEMO]\ntitle = "Invented physics"\ngroups = ["DEMO"]\n'
                    if index == 0
                    else '# Formatting and unrelated groups do not affect this render.\n[groups.OTHER]\ngroups = ["OTHER"]\n[groups.DEMO]\ngroups = [" DEMO ", "DEMO"]\ntitle = " Invented physics "\n'
                )
                environment = os.environ | {
                    "PYTHONHASHSEED": seed,
                    "TZ": zone,
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "analysis_lister",
                        "render-group",
                        "--group",
                        "DEMO",
                        "--snapshot",
                        str(source),
                        "--curation-config",
                        str(config),
                        "--output-dir",
                        str(output),
                    ],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                current = contents(output)
                self.assertEqual(len(current), 13)  # Four pages, report, eight assets.
                self.assertNotIn(str(work).encode(), current["view-report.json"])
                if baseline is None:
                    baseline = current
                else:
                    self.assertEqual(current, baseline)

    def test_profile_and_generator_hashes_are_recorded_and_effective(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "registry.json", root / "pages"
            source.write_text(json.dumps(fixture()))
            profile = GroupProfile(
                "DEMO", publication_policy=PublicationPolicy(groups=("DEMO",))
            )
            render_group(source, output, profile)
            first = json.loads((output / "view-report.json").read_text())
            self.assertEqual(
                first["profile_sha256"], json_fingerprint(first["profile"])
            )
            self.assertEqual(
                first["generator"]["content_sha256"], generator_fingerprint()
            )
            for path in output.glob("*.md"):
                self.assertIn(
                    "Render profile SHA-256: " + first["profile_sha256"],
                    path.read_text(),
                )
                self.assertIn(
                    "Generator contents SHA-256: "
                    + first["generator"]["content_sha256"],
                    path.read_text(),
                )
            assets_before = contents(output / "assets")
            render_group(
                source,
                output,
                GroupProfile(
                    "DEMO", publication_policy=PublicationPolicy(groups=("OTHER",))
                ),
            )
            second = json.loads((output / "view-report.json").read_text())
            self.assertNotEqual(first["profile_sha256"], second["profile_sha256"])
            self.assertEqual(first["snapshot"], second["snapshot"])
            self.assertEqual(first["generator"], second["generator"])
            self.assertEqual(assets_before, contents(output / "assets"))

    def test_fingerprints_ignore_location_mtimes_and_caches_but_track_code_and_assets(
        self,
    ):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "first"
            package.mkdir()
            (package / "module.py").write_text("original source")
            assets = package / "views/assets"
            assets.mkdir(parents=True)
            (assets / "example.js").write_text("original asset")
            original = generator_fingerprint(package)
            shutil.copytree(package, root / "second")
            self.assertEqual(original, generator_fingerprint(root / "second"))
            (package / "__pycache__").mkdir()
            (package / "__pycache__/module.pyc").write_bytes(b"bytecode")
            (package / "_source_revision.txt").write_text("a" * 40)
            os.utime(package / "module.py", ns=(1_000_000_000, 1_000_000_000))
            self.assertEqual(original, generator_fingerprint(package))
            (package / "module.py").write_text("edited source")
            changed = generator_fingerprint(package)
            self.assertNotEqual(original, changed)
            (assets / "example.js").write_text("edited asset")
            self.assertNotEqual(changed, generator_fingerprint(package))
            self.assertEqual(
                json_fingerprint({"a": 1, "b": 2}), json_fingerprint({"b": 2, "a": 1})
            )
