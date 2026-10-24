# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Carry the source Git revision into source archives and installed wheels."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

ROOT = Path(__file__).resolve().parent
spec = spec_from_file_location(
    "generator_provenance", ROOT / "analysis_lister/provenance.py"
)
provenance = module_from_spec(spec)
spec.loader.exec_module(provenance)


def record_revision(destination):
    path = Path(destination) / "analysis_lister" / provenance.REVISION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(provenance.generator_revision(ROOT) + "\n", encoding="utf-8")


class BuildWithRevision(build_py):
    def run(self):
        super().run()
        record_revision(self.build_lib)


class SourceWithRevision(sdist):
    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        record_revision(base_dir)


setup(cmdclass={"build_py": BuildWithRevision, "sdist": SourceWithRevision})
