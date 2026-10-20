# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Check built distributions using only the installed wheel and synthetic data.

Run after building and installing the wheel in a clean environment:
    python -I scripts/check_distribution.py
"""

import json
import subprocess
import sys
import tarfile
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory

import analysis_lister
from analysis_lister.citation_store import default_store_path, load_store
from analysis_lister.download import INTERMEDIATE_CA, trusted_ca_bundle
from analysis_lister.retrieval import load_scope


def main():
    root = Path(__file__).resolve().parents[1]
    installed = Path(analysis_lister.__file__).resolve()
    if installed.is_relative_to(root):
        raise RuntimeError("Check must import the installed wheel, not the checkout")

    package = distribution("glance-analysis-lister")
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
    assert load_scope().values == (80, 198, 205), "Wheel must bundle the TOPQ scope"
    citation_path = default_store_path()
    assert not citation_path.is_relative_to(root), "Must load installed citation data"
    assert citation_path.read_bytes() == (root / "json/doi_metadata.json").read_bytes()
    assert load_store(citation_path), "Installed citation dictionary must not be empty"
    with trusted_ca_bundle() as bundle:
        assert INTERMEDIATE_CA.read_bytes() in Path(bundle).read_bytes()

    archives = list((root / "dist").glob("*.tar.gz"))
    assert len(archives) == 1, "Expected one source distribution"
    with tarfile.open(archives[0]) as archive:
        names = [name for name in archive.getnames() if name.endswith("/LICENCE")]
        assert len(names) == 1, "Source distribution must contain LICENCE"
        assert archive.extractfile(names[0]).read() == licence
        prefix = names[0].removesuffix("LICENCE")
        scope_file = "analysis_lister/configs/topq.toml"
        assert (
            archive.extractfile(prefix + scope_file).read()
            == (root / scope_file).read_bytes()
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
        snapshot = root / "examples/synthetic_registry.json"
        lookup_flags = ["--lookup-dir", str(root / "examples/lookups")]
        output = work / "pages"
        notes = work / "obsidian_output"
        commands = [
            ["--help"],
            ["validate-lookups", *lookup_flags],
            [
                "resolve-dois",
                "--doi",
                "10.1007/JHEP07(2099)999",
                "--method",
                "infer",
                "--doi-cache",
                str(work / "citations.json"),
            ],
            [
                "render",
                "--snapshot",
                str(snapshot),
                "--output-dir",
                str(output),
                *lookup_flags,
            ],
            [
                "export-obsidian",
                "--snapshot",
                str(snapshot),
                "--output-dir",
                str(notes),
                *lookup_flags,
            ],
        ]
        executable = Path(sys.executable).parent / "analysis-lister"
        for command in commands:
            subprocess.run([str(executable), *command], cwd=work, check=True)
        subprocess.run(
            [sys.executable, "-I", "-m", "analysis_lister", "--help"],
            cwd=work,
            check=True,
        )
        assert len(list(output.rglob("*.md"))) == 13
        assert len(list((notes / "obs_published").glob("*.md"))) == 1
        assert len(list((notes / "obs_ongoing").glob("*.md"))) == 1
        citation = json.loads((work / "citations.json").read_text())[
            "10.1007/jhep07(2099)999"
        ]
        assert citation["citation"] == "JHEP 07 (2099) 999"
        assert citation["source"] == "doi-pattern:jhep"
        assert "locked" not in citation

    print("Installed CLI, synthetic rendering, TLS bundle and licences verified.")


if __name__ == "__main__":
    main()
