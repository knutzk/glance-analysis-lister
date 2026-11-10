# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build public documentation or preview it with selected local group pages."""

import argparse
import importlib
import json
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
PREVIEW_CONFIG = ".zensical-preview.yml"
GROUP_PREVIEW = Path(".cache/docs-group-preview")
GROUP_PAGES = {
    "Ongoing analyses": "ongoing.md",
    "Papers": "papers.md",
    "Conference notes": "confnotes.md",
    "Public notes": "pubnotes.md",
}
RELEASE_VERSIONS = ("v0.2.0", "v0.1.0")
if (ROOT / "analysis_lister/__init__.py").is_file():
    sys.path.insert(0, str(ROOT))
# Never stage the whole checkout or docs tree: they may contain private outputs.
PUBLIC_FILES = (
    "README.md",
    "LICENCE",
    *(f".github/release-notes/{version}.txt" for version in RELEASE_VERSIONS),
    "zensical.toml",
    "examples/demo/zensical.toml",
    "scripts/docs.py",
    "publication-curation.toml",
    "analysis_lister/registry/schemas/curated-v2.schema.json",
    "examples/README.md",
    "examples/synthetic_registry.json",
    "examples/demo/index.md",
    "examples/demo/publication-curation.toml",
    "docs/README.md",
    "docs/architecture.md",
    "docs/cern-demo.md",
    "docs/citations.md",
    "docs/cli-reference.md",
    "docs/compatibility.md",
    "docs/contributing-field.md",
    "docs/curated-format.md",
    "docs/development.md",
    "docs/diagnostics.md",
    "docs/glossary.md",
    "docs/provenance.md",
    "docs/ongoing.md",
    "docs/publications.md",
    "docs/python-access.md",
    "docs/registry.md",
    "docs/releases.md",
    "docs/rendering.md",
    "docs/site.md",
    "docs/troubleshooting.md",
    "docs/upgrading.md",
    "docs/stylesheets/site.css",
    "docs/workflows.md",
    "docs/images/README.md",
    "docs/images/command-flow.svg",
    "docs/images/ongoing.png",
    "docs/images/papers.png",
    "docs/images/ongoing-card.png",
    "docs/images/publication-row.png",
)


@lru_cache(maxsize=1)
def example_fragments(snapshot, policy):
    """Use the package's real views and controls with only the public fixture."""
    from attrs import evolve

    from analysis_lister.registry import CuratedRegistry
    from analysis_lister.views.markdown.ongoing import ongoing_cards
    from analysis_lister.views.markdown.papers import paper_table
    from analysis_lister.views.prepare import prepare_group

    registry = CuratedRegistry(json.loads(snapshot))
    view = prepare_group(registry, demo_profile(policy))
    # The explanatory guides discuss these specific records; the demo shows all.
    view = evolve(
        view,
        ongoing=tuple(
            row for row in view.ongoing if row.reference == "ANA-DEMO-2099-01"
        ),
        publications=tuple(
            row
            for row in view.publications
            if row.resource == "papers" and row.reference == "DEMO-2099-01"
        ),
    )
    return {"ongoing": ongoing_cards(view), "publications": paper_table(view)}


def demo_profile(policy):
    """Read the same explicit policy used by the standalone tutorial."""
    from analysis_lister.views.curation import load_publication_policy
    from analysis_lister.views.profiles import GroupProfile

    with TemporaryDirectory(prefix="glance-demo-policy-") as directory:
        path = Path(directory) / "publication-curation.toml"
        path.write_bytes(policy)
        publication_policy = load_publication_policy(path, "DEMO")
    if publication_policy is None:
        raise ValueError("The demo requires an explicit DEMO publication policy")
    return GroupProfile(
        "DEMO", title="Synthetic demo", publication_policy=publication_policy
    )


@lru_cache(maxsize=1)
def demo_pages(snapshot, policy):
    """Render only the fixed synthetic input; publish only the four demo pages."""
    from analysis_lister.views.build import render_group

    with TemporaryDirectory(prefix="glance-docs-demo-") as directory:
        work = Path(directory)
        source = work / "synthetic_registry.json"
        source.write_bytes(snapshot)
        render_group(source, work / "pages", demo_profile(policy))
        return {
            f"examples/demo/{name}.md": (work / "pages" / f"{name}.md").read_bytes()
            for name in ("ongoing", "papers", "confnotes", "pubnotes")
        }


def write_changed(destination, content):
    if not destination.exists() or destination.read_bytes() != content:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def stage(root=ROOT, *, include_roadmap=False, group_pages=()):
    """Stage public docs and explicitly selected local preview pages."""
    # Read all inputs before changing the staged copy (editors may replace files).
    sources = {name: (root / name).read_bytes() for name in PUBLIC_FILES}
    for version in RELEASE_VERSIONS:
        notes = sources.pop(f".github/release-notes/{version}.txt")
        heading = (
            f"# {version} release notes\n\n"
            "These repository notes describe this version. Commands and validation\n"
            "results below are historical; they do not qualify the current checkout.\n"
            "See [release qualification](../releases.md) and "
            "[upgrading](../upgrading.md).\n\n"
        )
        sources[f"docs/release-notes/{version}.md"] = heading.encode("utf-8") + notes
        # Keep source links usable on GitHub; the site links to rendered notes.
        sources["docs/releases.md"] = sources["docs/releases.md"].replace(
            f"(../.github/release-notes/{version}.txt)".encode(),
            f"(release-notes/{version}.md)".encode(),
        )
    destination = root / "site-src"
    if include_roadmap or group_pages:
        config = tomllib.loads(sources["zensical.toml"].decode("utf-8"))["project"]
    if include_roadmap:
        sources["ROADMAP.md"] = (root / "ROADMAP.md").read_bytes()
        config["nav"].append({"Roadmap": "ROADMAP.md"})
    if group_pages:
        destination = root / GROUP_PREVIEW / "site-src"
        config["docs_dir"] = (GROUP_PREVIEW / "site-src").as_posix()
        config["site_dir"] = (GROUP_PREVIEW / "site").as_posix()
        config["site_name"] += " · local data"
        position = next(
            (i + 1 for i, entry in enumerate(config["nav"]) if "Demo" in entry),
            len(config["nav"]),
        )
        for group, directory in group_pages:
            prefix = f"local-groups/{group.lower()}"
            for filename in GROUP_PAGES.values():
                sources[f"{prefix}/{filename}"] = (directory / filename).read_bytes()
            config["nav"].insert(
                position,
                {
                    f"{group} (local data)": [
                        {title: f"{prefix}/{filename}"}
                        for title, filename in GROUP_PAGES.items()
                    ]
                },
            )
            position += 1
    if include_roadmap or group_pages:
        # JSON is valid YAML; Zensical accepts the same project settings in both.
        # Keep this generated config at the repository root for relative paths.
        write_changed(
            root / PREVIEW_CONFIG,
            (json.dumps(config, indent=2) + "\n").encode("utf-8"),
        )
    snapshot = sources["examples/synthetic_registry.json"]
    policy = sources["examples/demo/publication-curation.toml"]
    sources.update(demo_pages(snapshot, policy))
    for name, fragment in example_fragments(snapshot, policy).items():
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
    for component in ("common", "ongoing", "papers", "notes"):
        for extension in ("css", "js"):
            filename = f"gal-{component}.{extension}"
            sources[f"docs/assets/{filename}"] = (
                files("analysis_lister.views") / "assets" / filename
            ).read_bytes()
    for name, content in sources.items():
        write_changed(destination / name, content)


def group_pages_argument(value):
    group, separator, directory = value.partition("=")
    if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_-]*", group) or not directory:
        raise argparse.ArgumentTypeError("Use GROUP=PATH, for example TOPQ=pages/topq")
    return group, Path(directory).resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "serve"))
    parser.add_argument("--dev-addr", default="127.0.0.1:8000")
    parser.add_argument(
        "--group-pages",
        type=group_pages_argument,
        action="append",
        default=[],
        metavar="GROUP=PATH",
        help="Include rendered group pages in the local preview; repeat for more groups",
    )
    args = parser.parse_args()
    if args.group_pages:
        if args.command != "serve":
            parser.error(
                "--group-pages is available only with serve, not public builds"
            )
        if args.dev_addr.rpartition(":")[0] not in {"127.0.0.1", "localhost", "[::1]"}:
            parser.error("Group-page previews must bind to a loopback address")
        groups = [group for group, _ in args.group_pages]
        if len(set(groups)) != len(groups):
            parser.error("Specify each preview group only once")
        for _, directory in args.group_pages:
            if any(
                directory.is_relative_to((ROOT / output).resolve())
                for output in ("site-src", "site", GROUP_PREVIEW)
            ):
                parser.error(
                    "Group pages must be outside generated documentation directories"
                )
            missing = [
                name
                for name in GROUP_PAGES.values()
                if not (directory / name).is_file()
            ]
            if missing:
                parser.error(
                    f"Missing rendered pages in {directory}: {', '.join(missing)}"
                )
    # Check the renderer's dependencies before clearing an existing preview.
    try:
        importlib.import_module("zensical")
        example_fragments(
            (ROOT / "examples/synthetic_registry.json").read_bytes(),
            (ROOT / "examples/demo/publication-curation.toml").read_bytes(),
        )
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
    directories = (
        (GROUP_PREVIEW / "site-src", GROUP_PREVIEW / "site")
        if args.group_pages
        else ("site-src", "site")
    )
    for directory in directories:
        path = ROOT / directory
        if path.exists():
            shutil.rmtree(path)
    include_roadmap = args.command == "serve" and (ROOT / "ROADMAP.md").is_file()
    stage(include_roadmap=include_roadmap, group_pages=args.group_pages)
    config = PREVIEW_CONFIG if include_roadmap or args.group_pages else "zensical.toml"
    command = [sys.executable, "-m", "zensical", args.command, "-f", config]
    if args.command == "build":
        return subprocess.call([*command, "--clean", "--strict"], cwd=ROOT)
    with subprocess.Popen([*command, "--dev-addr", args.dev_addr], cwd=ROOT) as process:
        # A supervisor may terminate only this wrapper. Handle SIGTERM like
        # Ctrl+C so the Zensical child is stopped before a subsequent build.
        previous_termination = signal.signal(signal.SIGTERM, signal.default_int_handler)
        try:
            while process.poll() is None:
                time.sleep(0.5)
                try:
                    stage(include_roadmap=include_roadmap, group_pages=args.group_pages)
                except FileNotFoundError:
                    # Retry while an editor is replacing a source file.
                    continue
        except KeyboardInterrupt:
            return 0
        finally:
            signal.signal(signal.SIGTERM, previous_termination)
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
