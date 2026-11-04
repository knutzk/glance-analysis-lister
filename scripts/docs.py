# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build or preview documentation from an explicit list of public files."""

import argparse
import importlib
import json
import shlex
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "analysis_lister/__init__.py").is_file():
    sys.path.insert(0, str(ROOT))
# Never stage the whole checkout or docs tree: they may contain private outputs.
PUBLIC_FILES = (
    "README.md",
    "LICENCE",
    "zensical.toml",
    "scripts/docs.py",
    "publication-curation.toml",
    "analysis_lister/registry/schemas/curated-v2.schema.json",
    "examples/README.md",
    "examples/synthetic_registry.json",
    "docs/README.md",
    "docs/architecture.md",
    "docs/citations.md",
    "docs/curated-format.md",
    "docs/development.md",
    "docs/diagnostics.md",
    "docs/provenance.md",
    "docs/ongoing.md",
    "docs/publications.md",
    "docs/python-access.md",
    "docs/registry.md",
    "docs/rendering.md",
    "docs/site.md",
    "docs/stylesheets/site.css",
    "docs/workflows.md",
    "docs/images/README.md",
    "docs/images/ongoing.png",
    "docs/images/papers.png",
    "docs/images/ongoing-card.png",
    "docs/images/publication-row.png",
)


@lru_cache(maxsize=1)
def example_fragments(snapshot):
    """Use the package's real views and controls with only the public fixture."""
    from analysis_lister.registry import CuratedRegistry
    from analysis_lister.views.markdown.ongoing import ongoing_cards
    from analysis_lister.views.markdown.papers import paper_table
    from analysis_lister.views.prepare import prepare_group
    from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

    registry = CuratedRegistry(json.loads(snapshot))
    view = prepare_group(
        registry,
        GroupProfile("DEMO", publication_policy=PublicationPolicy(groups=("DEMO",))),
    )
    return {"ongoing": ongoing_cards(view), "publications": paper_table(view)}


def stage(root=ROOT):
    """Copy changed public sources without rewriting unchanged files."""
    # Read all inputs before changing the staged copy (editors may replace files).
    sources = {name: (root / name).read_bytes() for name in PUBLIC_FILES}
    for name, fragment in example_fragments(
        sources["examples/synthetic_registry.json"]
    ).items():
        page = f"docs/{name}.md"
        text = sources[page].decode("utf-8")
        start, end = f"<!-- BEGIN LIVE {name} -->", f"<!-- END LIVE {name} -->"
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError(f"Expected one live-example block in {page}")
        before, rest = text.split(start)
        _, after = rest.split(end)
        sources[page] = (
            before + '<div class="gal-doc-example">\n' + fragment + "</div>\n" + after
        ).encode("utf-8")
    for component in ("common", "ongoing", "papers"):
        for extension in ("css", "js"):
            filename = f"gal-{component}.{extension}"
            sources[f"docs/assets/{filename}"] = (
                files("analysis_lister.views") / "assets" / filename
            ).read_bytes()
    for name, content in sources.items():
        destination = root / "site-src" / name
        if not destination.exists() or destination.read_bytes() != content:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "serve"))
    parser.add_argument("--dev-addr", default="127.0.0.1:8000")
    args = parser.parse_args()
    # Check the renderer's dependencies before clearing an existing preview.
    try:
        importlib.import_module("zensical")
        example_fragments((ROOT / "examples/synthetic_registry.json").read_bytes())
    except ModuleNotFoundError as error:
        parser.exit(
            1,
            f"Missing documentation dependency: {error.name}\n"
            f"Python environment: {sys.executable}\n"
            "From the repository root, install the documentation requirements:\n"
            f"  {shlex.quote(sys.executable)} -m pip install -r requirements-docs.txt\n"
            "Or activate the prepared environment: source .venv/bin/activate\n",
        )
    # These directories are disposable outputs owned by this command. Clear old
    # content so a previous preview cannot leak extra files into a later build.
    for directory in ("site-src", "site"):
        path = ROOT / directory
        if path.exists():
            shutil.rmtree(path)
    stage()
    command = [sys.executable, "-m", "zensical", args.command]
    if args.command == "build":
        return subprocess.call([*command, "--clean", "--strict"], cwd=ROOT)
    with subprocess.Popen([*command, "--dev-addr", args.dev_addr], cwd=ROOT) as process:
        try:
            while process.poll() is None:
                time.sleep(0.5)
                try:
                    stage()
                except FileNotFoundError:
                    # Retry while an editor is replacing a source file.
                    continue
        except KeyboardInterrupt:
            return 0
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait()
        return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
