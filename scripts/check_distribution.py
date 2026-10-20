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
from analysis_lister.download import INTERMEDIATE_CA, trusted_ca_bundle
from analysis_lister.lookup_dicts.short_titles import ShortTitles


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
    assert not ShortTitles, "Public wheel must have empty short-title defaults"
    with trusted_ca_bundle() as bundle:
        assert INTERMEDIATE_CA.read_bytes() in Path(bundle).read_bytes()

    archives = list((root / "dist").glob("*.tar.gz"))
    assert len(archives) == 1, "Expected one source distribution"
    with tarfile.open(archives[0]) as archive:
        names = [name for name in archive.getnames() if name.endswith("/LICENCE")]
        assert len(names) == 1, "Source distribution must contain LICENCE"
        assert archive.extractfile(names[0]).read() == licence

    with TemporaryDirectory() as directory:
        work = Path(directory)
        snapshot = work / "synthetic.json"
        snapshot.write_text(json.dumps({"entries": {}, "threshold_year": "2020"}))
        output = work / "pages"
        commands = [
            ["--help"],
            ["validate-lookups"],
            ["render", "--snapshot", str(snapshot), "--output-dir", str(output)],
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

    print("Installed CLI, synthetic rendering, TLS bundle and licences verified.")


if __name__ == "__main__":
    main()
