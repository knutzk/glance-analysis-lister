# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Check built distributions using only the installed wheel and synthetic data.

Run after building and installing the wheel in a clean environment:
    python -I scripts/check_distribution.py
"""

import csv
import json
import subprocess
import sys
import tarfile
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory

import analysis_lister
from analysis_lister.citations.store import default_store_path, load_store
from analysis_lister.downloaders.html import download_tasks
from analysis_lister.downloaders.http import INTERMEDIATE_CA, trusted_ca_bundle
from analysis_lister.downloaders.manifest import make_manifest
from analysis_lister.registry import CuratedRegistry
from analysis_lister.storage import SUPPLEMENT_MANIFEST
from analysis_lister.views.curation import (
    default_curation_path,
    load_publication_policy,
)


def main():
    root = Path(__file__).resolve().parents[1]
    installed = Path(analysis_lister.__file__).resolve()
    if installed.is_relative_to(root):
        raise RuntimeError("Check must import the installed wheel, not the checkout")

    package = distribution("glance-analysis-lister")
    retired = (
        "analysis_lister/configs/",
        "analysis_lister/downloaders/scope.py",
        "analysis_lister/glance/",
        "analysis_lister/markdown/",
        "analysis_lister/lookup_dicts/",
        "analysis_lister/render.py",
        "analysis_lister/obsidian.py",
        "analysis_lister/lookup_review.py",
        "analysis_lister/lookup_validation.py",
        "analysis_lister/citation_store.py",
        "analysis_lister/doi_resolver.py",
        "analysis_lister/registry/doi.py",
        "analysis_lister/downloaders/publication.py",
        "analysis_lister/views/selection.py",
        "analysis_lister/views/semantics.py",
        "analysis_lister/views/markdown/cards.py",
        "analysis_lister/views/markdown/archive.py",
        "analysis_lister/views/markdown/filtering.py",
        "analysis_lister/views/markdown/publication_filtering.py",
    )
    assert not any(str(path).startswith(retired) for path in package.files), (
        "Retired modules must not ship in the wheel"
    )
    assert package.metadata["License-Expression"] == "GPL-3.0-only"
    assert package.metadata["License-File"] == "LICENCE"
    licences = [
        path
        for path in package.files or []
        if str(path).endswith(".dist-info/licenses/LICENCE")
    ]
    assert len(licences) == 1, "Wheel must contain LICENCE"
    licence = (root / "LICENCE").read_bytes()
    assert package.locate_file(licences[0]).read_bytes() == licence
    citation_path = default_store_path()
    assert not citation_path.is_relative_to(root), "Must load installed citation data"
    assert citation_path.read_bytes() == (root / "json/doi_metadata.json").read_bytes()
    assert load_store(citation_path), "Installed citation dictionary must not be empty"
    policy_path = default_curation_path()
    assert not policy_path.is_relative_to(root), (
        "Must load installed publication policy"
    )
    assert policy_path.read_bytes() == (root / "publication-curation.toml").read_bytes()
    assert load_publication_policy(policy_path, "TOPQ") is not None
    with trusted_ca_bundle() as bundle:
        assert INTERMEDIATE_CA.read_bytes() in Path(bundle).read_bytes()

    archives = list((root / "dist").glob("*.tar.gz"))
    assert len(archives) == 1, "Expected one source distribution"
    with tarfile.open(archives[0]) as archive:
        names = [name for name in archive.getnames() if name.endswith("/LICENCE")]
        assert len(names) == 1, "Source distribution must contain LICENCE"
        assert archive.extractfile(names[0]).read() == licence
        prefix = names[0].removesuffix("LICENCE")
        assert (
            archive.extractfile(prefix + "publication-curation.toml").read()
            == (root / "publication-curation.toml").read_bytes()
        )
        sample = "examples/synthetic_registry.json"
        assert (
            archive.extractfile(prefix + sample).read() == (root / sample).read_bytes()
        )
        assert (
            archive.extractfile(prefix + "json/doi_metadata.json").read()
            == (root / "json/doi_metadata.json").read_bytes()
        )

    with TemporaryDirectory() as directory:
        work = Path(directory)
        commands = [
            ["--help"],
            ["download-api", "--help"],
            ["download-html", "--help"],
            ["render-group", "--help"],
            [
                "resolve-dois",
                "--doi",
                "10.1007/JHEP07(2099)999",
                "--method",
                "infer",
                "--doi-cache",
                str(work / "citations.json"),
            ],
        ]
        executable = Path(sys.executable).parent / "analysis-lister"
        for command in commands:
            subprocess.run([str(executable), *command], cwd=work, check=True)
        for command in ("render", "export-obsidian", "validate-lookups"):
            rejected = subprocess.run(
                [str(executable), command], cwd=work, capture_output=True
            )
            assert rejected.returncode == 2, "Retired commands must be rejected"
        example_output = work / "example-pages"
        subprocess.run(
            [
                str(executable),
                "render-group",
                "--group",
                "DEMO",
                "--snapshot",
                str(root / "examples/synthetic_registry.json"),
                "--output-dir",
                str(example_output),
            ],
            cwd=work,
            check=True,
        )
        example_report = json.loads((example_output / "view-report.json").read_text())
        assert example_report["counts"]["archive_publications"] == 3
        api_input = work / "api.json"
        supplemental = work / "supplemental"
        supplemental.mkdir()
        tasks = download_tasks()
        (supplemental / SUPPLEMENT_MANIFEST).write_text(
            json.dumps(make_manifest(tasks))
        )
        resources = ("analyses", "papers", "confnotes", "pubnotes")
        raw = {
            "schema": "glance-api-registry",
            "schema_version": 1,
            "fetched_at": "2099-01-01T00:00:00+00:00",
            "source": {
                "selection": "all-accessible",
                "base_url": "https://example.test/api",
            },
            "counts": dict.fromkeys(resources, 1),
        }
        for resource, prefix in zip(
            resources, ("ANA-", "", "CONF-", "PUB-"), strict=True
        ):
            key = (
                "temporaryReferenceCode"
                if resource in {"confnotes", "pubnotes"}
                else "referenceCode"
            )
            raw[resource] = [
                {
                    key: prefix + "DEMO-2099-01",
                    "analysisTeam": [
                        {
                            "firstName": "Invented",
                            "lastName": "Editor",
                            "isContactEditor": True,
                        }
                    ],
                    "metadata": {"keywords": [{"name": "Synthetic"}]},
                }
            ]
        for task in tasks:
            row = dict.fromkeys(task.columns, "")
            key = (
                "temporaryReferenceCode" if task.name == "pubnotes" else "referenceCode"
            )
            row[task.key] = raw[task.name][0][key]
            with (supplemental / task.csv_filename).open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=task.columns)
                writer.writeheader()
                writer.writerow(row)
        raw["papers"][0]["publicationPhase"] = {
            "finalJournalPublicationUrls": [
                {"url": "https://doi.org/10.1007/JHEP07(2099)999"}
            ],
        }
        raw["analyses"][0]["status"] = "Phase 0 Active"
        raw["analyses"][0]["groups"] = {
            "leadingGroup": {"name": "DEMO"},
            "leadingSubgroup": None,
            "otherGroups": [],
            "subgroups": [],
        }
        raw["analyses"][0]["phase0"] = {"startDate": "2099-01-01"}
        api_input.write_text(json.dumps(raw))
        curated_path = work / "curated.json"
        subprocess.run(
            [
                str(executable),
                "build-registry",
                "--api-snapshot",
                str(api_input),
                "--csv-dir",
                str(supplemental),
                "--output",
                str(curated_path),
                "--doi-cache",
                str(work / "citations.json"),
            ],
            cwd=work,
            check=True,
        )
        reader = CuratedRegistry.from_json(curated_path)
        assert len(reader.records("papers")) == 1
        assert reader.get("analyses", "ANA-DEMO-2099-01") is not None
        curated = json.loads(curated_path.read_text())
        assert curated["schema"] == "glance-curated-registry"
        assert curated["analyses"][0]["gal_contactEditors"] == ["Invented Editor"]
        assert curated["analyses"][0]["metadata"]["gal_keywords"] == ["Synthetic"]
        assert "analysisTeam" not in curated["analyses"][0]
        assert (
            curated["papers"][0]["publicationPhase"]["gal_dois"][0]["citation"]
            == "JHEP 07 (2099) 999"
        )
        group_output = work / "group-pages"
        subprocess.run(
            [
                str(executable),
                "render-group",
                "--group",
                "DEMO",
                "--snapshot",
                str(curated_path),
                "--output-dir",
                str(group_output),
            ],
            cwd=work,
            check=True,
        )
        assert not (group_output / "index.md").exists()
        assert not (group_output / "publications.md").exists()
        assert (group_output / "ongoing.md").is_file()
        assert "gal-papers" in (group_output / "papers.md").read_text()
        assert (group_output / "confnotes.md").is_file()
        assert (group_output / "pubnotes.md").is_file()
        assert "data-gal-item" in (group_output / "ongoing.md").read_text()
        for name in (
            "gal-common.js",
            "gal-ongoing.js",
            "gal-common.css",
            "gal-ongoing.css",
            "gal-papers.js",
            "gal-papers.css",
            "gal-notes.js",
            "gal-notes.css",
        ):
            assert (group_output / "assets" / name).read_bytes() == (
                root / "analysis_lister/views/assets" / name
            ).read_bytes()
        report = json.loads((group_output / "view-report.json").read_text())
        assert report["counts"]["ongoing_analyses"] == 1
        subprocess.run(
            [sys.executable, "-I", "-m", "analysis_lister", "--help"],
            cwd=work,
            check=True,
        )
        citation = json.loads((work / "citations.json").read_text())[
            "10.1007/jhep07(2099)999"
        ]
        assert citation["citation"] == "JHEP 07 (2099) 999"
        assert citation["source"] == "doi-pattern:jhep"
        assert "locked" not in citation

    print("Installed CLI, synthetic rendering, TLS bundle and licences verified.")


if __name__ == "__main__":
    main()
