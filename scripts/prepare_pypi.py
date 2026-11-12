# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Validate published GitHub release assets for a separate, approved PyPI upload.

This script only downloads and validates files; it never uploads to an index.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from email.parser import BytesParser
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

REPOSITORY = "knutzk/glance-analysis-lister"
PROJECT = "glance-analysis-lister"


def release_assets(release, tag):
    """Require a published regular release with exactly the expected distributions."""
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("Choose a regular release tag such as v0.4.0")
    if (
        release.get("tag_name") != tag
        or release.get("draft") is not False
        or release.get("prerelease") is not False
        or not release.get("published_at")
    ):
        raise ValueError("The tag must identify a published, non-prerelease release")
    prefix = f"glance_analysis_lister-{tag[1:]}"
    expected = {f"{prefix}-py3-none-any.whl", f"{prefix}.tar.gz"}
    assets = [
        asset
        for asset in release.get("assets", [])
        if asset.get("name", "").endswith((".whl", ".tar.gz", ".zip"))
    ]
    if len(assets) != 2 or {asset["name"] for asset in assets} != expected:
        raise ValueError("Expected exactly the version's wheel and source archive")
    for asset in assets:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
            raise ValueError("Every distribution must have a GitHub SHA-256 digest")
    return assets


def check_metadata(path, version):
    """Read metadata without extracting or executing the distribution."""
    if path.suffix == ".whl":
        with ZipFile(path) as archive:
            candidates = [
                item
                for item in archive.infolist()
                if item.filename.endswith(".dist-info/METADATA")
            ]
            if len(candidates) != 1 or candidates[0].file_size > 1_000_000:
                raise ValueError("Wheel must have one bounded METADATA file")
            metadata = archive.read(candidates[0])
    else:
        with tarfile.open(path) as archive:
            expected = f"glance_analysis_lister-{version}/PKG-INFO"
            candidates = [item for item in archive if item.name == expected]
            if (
                len(candidates) != 1
                or not candidates[0].isfile()
                or candidates[0].size > 1_000_000
            ):
                raise ValueError("Source archive must have one bounded PKG-INFO file")
            metadata = archive.extractfile(candidates[0]).read()
    parsed = BytesParser().parsebytes(metadata)
    names = parsed.get_all("Name", [])
    versions = parsed.get_all("Version", [])
    if (
        len(names) != 1
        or re.sub(r"[-_.]+", "-", names[0]).lower() != PROJECT
        or versions != [version]
    ):
        raise ValueError("Distribution metadata does not match the project and tag")


def prepare(release, tag, downloaded, output):
    """Stage only verified, unchanged distribution bytes in a new directory."""
    assets = release_assets(release, tag)
    hashes = []
    for asset in assets:
        path = downloaded / asset["name"]
        if path.is_symlink() or not path.is_file():
            raise ValueError("Downloaded distribution must be a regular file")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if f"sha256:{digest}" != asset["digest"]:
            raise ValueError(f"SHA-256 mismatch for {asset['name']}")
        check_metadata(path, tag[1:])
        hashes.append(f"{digest}  {asset['name']}")
    output.mkdir(parents=True, exist_ok=False)
    for asset in assets:
        shutil.copyfile(downloaded / asset["name"], output / asset["name"])
    return "\n".join(hashes) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Validate before using the tag in any API path or external command.
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.tag):
        parser.error("Expected a regular vMAJOR.MINOR.PATCH release tag")
    release = json.loads(
        subprocess.check_output(
            ["gh", "api", f"repos/{REPOSITORY}/releases/tags/{args.tag}"], text=True
        )
    )
    assets = release_assets(release, args.tag)
    with TemporaryDirectory(prefix="glance-pypi-download-") as directory:
        downloaded = Path(directory)
        command = [
            "gh",
            "release",
            "download",
            args.tag,
            "--repo",
            REPOSITORY,
            "--dir",
            str(downloaded),
        ]
        for asset in assets:
            command.extend(["--pattern", asset["name"]])
        subprocess.run(command, check=True)
        hashes = prepare(release, args.tag, downloaded, args.output)
    summary = (
        f"### Validated {args.tag} for PyPI\n\n"
        f"Source: https://github.com/{REPOSITORY}/releases/tag/{args.tag}\n\n"
        "The wheel and source archive match GitHub's recorded SHA-256 digests. "
        "No rebuild or metadata rewrite was performed.\n\n"
        f"```text\n{hashes}```\n\n"
        "Preparation does not publish. An upload requires the separate gated job.\n"
    )
    print(summary)
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(destination).open("a") as stream:
            stream.write(summary)


if __name__ == "__main__":
    main()
