# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""PyPI preparation rejects altered artifacts and never publishes packages."""

import hashlib
import io
import tarfile
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.prepare_pypi import check_metadata, prepare, release_assets

TAG = "v0.9.0"
WHEEL = "glance_analysis_lister-0.9.0-py3-none-any.whl"
SDIST = "glance_analysis_lister-0.9.0.tar.gz"


def make_release(directory):
    metadata = b"Metadata-Version: 2.4\nName: glance-analysis-lister\nVersion: 0.9.0\n"
    with ZipFile(directory / WHEEL, "w") as archive:
        archive.writestr("glance_analysis_lister-0.9.0.dist-info/METADATA", metadata)
    with tarfile.open(directory / SDIST, "w:gz") as archive:
        info = tarfile.TarInfo("glance_analysis_lister-0.9.0/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))
    return {
        "tag_name": TAG,
        "draft": False,
        "prerelease": False,
        "published_at": "2099-01-01T00:00:00Z",
        "assets": [
            {
                "name": name,
                "digest": "sha256:"
                + hashlib.sha256((directory / name).read_bytes()).hexdigest(),
            }
            for name in (WHEEL, SDIST)
        ],
    }


class PreparePyPITests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.downloaded = self.root / "downloaded"
        self.downloaded.mkdir()
        self.release = make_release(self.downloaded)
        self.output = self.root / "dist"

    def test_verified_assets_are_copied_without_changes(self):
        summary = prepare(self.release, TAG, self.downloaded, self.output)
        self.assertEqual({p.name for p in self.output.iterdir()}, {WHEEL, SDIST})
        for asset in self.release["assets"]:
            name = asset["name"]
            self.assertEqual(
                (self.output / name).read_bytes(), (self.downloaded / name).read_bytes()
            )
            self.assertIn(asset["digest"][7:] + "  " + name, summary)

    def test_unpublished_mismatched_or_prerelease_is_rejected(self):
        for field, value in (
            ("draft", True),
            ("prerelease", True),
            ("tag_name", "v0.8.0"),
            ("published_at", None),
        ):
            release = deepcopy(self.release)
            release[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare(release, TAG, self.downloaded, self.output)
            self.assertFalse(self.output.exists())

    def test_invalid_tag_and_unexpected_distribution_names_are_rejected(self):
        for tag in ("../main", "v0.9.0rc1", "v01.0.0", "main", "v0.9.0; echo injected"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release_assets(self.release, tag)
        for names in (
            [WHEEL],
            [WHEEL, SDIST, WHEEL],
            ["../" + WHEEL, SDIST],
            [WHEEL, SDIST, "extra.zip"],
        ):
            release = deepcopy(self.release)
            release["assets"] = [
                {"name": name, "digest": "sha256:" + "a" * 64} for name in names
            ]
            with self.subTest(names=names), self.assertRaises(ValueError):
                release_assets(release, TAG)

    def test_missing_digest_and_changed_bytes_are_rejected_before_staging(self):
        for digest in (None, "", "sha256:bad", "md5:" + "a" * 32, "sha256:" + "a" * 64):
            release = deepcopy(self.release)
            release["assets"][1]["digest"] = digest
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                prepare(release, TAG, self.downloaded, self.output)
            self.assertFalse(self.output.exists())

    def test_metadata_must_match_project_and_version(self):
        for metadata in (
            b"Name: other-project\nVersion: 0.9.0\n",
            b"Name: other-distribution\nVersion: 0.9.0\n",
            b"Name: glance-analysis-lister\nVersion: 0.8.0\n",
            b"Name: glance-analysis-lister\nVersion: 0.9.0\nVersion: 0.8.0\n",
        ):
            with ZipFile(self.downloaded / WHEEL, "w") as archive:
                archive.writestr("example.dist-info/METADATA", metadata)
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                check_metadata(self.downloaded / WHEEL, "0.9.0")

    def test_ambiguous_or_missing_metadata_is_rejected(self):
        with ZipFile(self.downloaded / WHEEL, "w") as archive:
            for name in ("one", "two"):
                archive.writestr(f"{name}.dist-info/METADATA", b"Name: example\n")
        with self.assertRaises(ValueError):
            check_metadata(self.downloaded / WHEEL, "0.9.0")
        with tarfile.open(self.downloaded / SDIST, "w:gz"):
            pass
        with self.assertRaises(ValueError):
            check_metadata(self.downloaded / SDIST, "0.9.0")

    def test_existing_output_and_symlinked_inputs_are_not_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaises(FileExistsError):
            prepare(self.release, TAG, self.downloaded, self.output)
        self.assertEqual(sentinel.read_text(), "keep")
        wheel = self.downloaded / WHEEL
        moved = self.root / "original.whl"
        wheel.rename(moved)
        wheel.symlink_to(moved)
        with self.assertRaises(ValueError):
            prepare(self.release, TAG, self.downloaded, self.root / "other")

    def test_other_distribution_names_are_rejected(self):
        release = deepcopy(self.release)
        for asset in release["assets"]:
            asset["name"] = asset["name"].replace(
                "glance_analysis_lister", "other_distribution"
            )
        with self.assertRaisesRegex(ValueError, "Expected exactly"):
            prepare(release, TAG, self.downloaded, self.output)
        self.assertFalse(self.output.exists())

    def test_historical_regular_versions_are_allowed(self):
        for version in ("0.1.0", "0.2.0", "0.3.0"):
            release = deepcopy(self.release)
            release["tag_name"] = f"v{version}"
            for asset in release["assets"]:
                asset["name"] = asset["name"].replace("0.9.0", version)
            self.assertEqual(len(release_assets(release, f"v{version}")), 2)
