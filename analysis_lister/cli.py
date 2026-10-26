# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Command-line interface for analysis data maintenance and page generation."""

import argparse
import logging
from pathlib import Path

import requests

from .citations.store import default_store_path
from .console import configure_logging, print_summary
from .downloaders.api import DEFAULT_PAGE_SIZE
from .views.curation import default_curation_path

logger = logging.getLogger(__name__)

API_SNAPSHOT_PATH = Path("glance_api_registry.json")
CURATED_SNAPSHOT_PATH = Path("glance_curated_registry.json")


def _validate_html_download(command, args):
    if args.from_html is not None and args.save_html is not None:
        command.error("--from-html cannot be combined with --save-html")
    if (
        args.save_html is not None
        and args.save_html.resolve() == args.csv_dir.resolve()
    ):
        command.error("--save-html and --csv-dir must use separate directories")


def _positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _validate_resolution(command, args):
    if (
        args.snapshot is not None
        and args.snapshot.resolve() == args.doi_cache.resolve()
    ):
        command.error("Citation cache must not overwrite the input snapshot")


def parser():
    """Register commands with their option groups, handlers, and validation."""
    console = argparse.ArgumentParser(add_help=False)
    verbosity = console.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Show detailed logging with timestamps and module names.",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Show only warnings and errors, plus final results.",
    )
    console.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default=argparse.SUPPRESS,
        help="Colour output (default: auto; respects NO_COLOR).",
    )
    citations = argparse.ArgumentParser(add_help=False)
    citations.add_argument(
        "--doi-cache",
        type=Path,
        default=default_store_path(),
        help="Maintained citation JSON dictionary (default: shared glance-analysis-lister dictionary).",
    )
    counts = argparse.ArgumentParser(add_help=False)
    counts.add_argument(
        "--allow-count-drop",
        action="store_true",
        help="Allow an understood drop in registry counts; other checks still apply.",
    )

    command = argparse.ArgumentParser(description=__doc__, parents=[console])
    command.set_defaults(validator=None)
    commands = command.add_subparsers(dest="command", required=True)
    api = commands.add_parser(
        "download-api",
        help="Download the API source registry using browser SSO.",
        parents=[console, counts],
    )
    api.add_argument(
        "--output",
        type=Path,
        default=API_SNAPSHOT_PATH,
        help="API source JSON destination (default: %(default)s).",
    )
    api.add_argument(
        "--login", action="store_true", help="Open CERN SSO in your browser."
    )
    api.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Records requested per API page (default: %(default)s); larger sizes require server support and may not be faster.",
    )
    api.set_defaults(handler=_run_download_api)
    refresh = commands.add_parser(
        "refresh",
        parents=[console, counts, citations],
        help="Download once, build a registry and render selected groups sequentially.",
    )
    refresh.add_argument(
        "--groups", nargs="+", required=True, help="Group tokens, e.g. TOPQ HIGP."
    )
    refresh.add_argument("--api-snapshot", type=Path, default=API_SNAPSHOT_PATH)
    refresh.add_argument(
        "--snapshot",
        type=Path,
        default=CURATED_SNAPSHOT_PATH,
        help="Curated registry destination.",
    )
    refresh.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pages"),
        help="One group: write directly here. Multiple groups: lowercase group subdirectories (default: %(default)s).",
    )
    refresh.add_argument(
        "--curation-config", type=Path, default=default_curation_path()
    )
    refresh.add_argument(
        "--login", action="store_true", help="Open CERN SSO in your browser."
    )
    refresh.add_argument("--page-size", type=_positive_int, default=DEFAULT_PAGE_SIZE)
    refresh.set_defaults(handler=_run_refresh)
    html = commands.add_parser(
        "download-html",
        help="Fallback: download GLANCE HTML tables as standalone CSVs.",
        description="Download all four GLANCE HTML tables as CSVs. These are independent exports, not inputs to build-registry. Requires the html extra; Chrome is required for --login.",
        parents=[console],
    )
    html.add_argument(
        "--csv-dir",
        type=Path,
        default=Path("."),
        help="CSV output directory (default: current working directory).",
    )
    source = html.add_mutually_exclusive_group()
    source.add_argument(
        "--login",
        action="store_true",
        help="Log in manually using Chrome and save fresh cookies.",
    )
    source.add_argument(
        "--from-html",
        type=Path,
        metavar="DIR",
        help="Replay saved HTML and its manifest from DIR without network access.",
    )
    html.add_argument(
        "--save-html",
        type=Path,
        metavar="DIR",
        help="Save downloaded HTML and its manifest to DIR for offline replay.",
    )
    html.add_argument(
        "--cookies",
        type=Path,
        default=Path("cookies.json"),
        help="Session cookie file (default: %(default)s).",
    )
    html.set_defaults(handler=_run_download_html, validator=_validate_html_download)
    build = commands.add_parser(
        "build-registry",
        help="Build a curated registry from API JSON and shared identifier/citation data.",
        parents=[counts, citations, console],
    )
    build.set_defaults(handler=_run_build_registry)
    build.add_argument(
        "--api-snapshot",
        type=Path,
        default=API_SNAPSHOT_PATH,
        help="API JSON input (default: %(default)s).",
    )
    build.add_argument(
        "--output",
        type=Path,
        default=CURATED_SNAPSHOT_PATH,
        help="Curated JSON output (default: %(default)s).",
    )
    compare = commands.add_parser(
        "compare-snapshots",
        parents=[console],
        help="Compare two saved API or two curated snapshots offline.",
        description="Compare records by native identifier. Container timestamps and build metadata are ignored; list order is significant. No live requests.",
    )
    compare.add_argument("before", type=Path, help="Previous snapshot.")
    compare.add_argument("after", type=Path, help="New snapshot in the same format.")
    compare.add_argument(
        "--details",
        action="store_true",
        help="List added/removed identifiers and changed field paths, without record values.",
    )
    compare.add_argument(
        "--output",
        type=Path,
        help="Write a detailed JSON report including before/after field values.",
    )
    compare.set_defaults(handler=_run_compare_snapshots)
    group = commands.add_parser(
        "render-group",
        parents=[console],
        help="Render ongoing analyses and separate publication pages.",
    )
    group.add_argument(
        "--snapshot",
        type=Path,
        default=CURATED_SNAPSHOT_PATH,
        help="Curated registry JSON (default: %(default)s).",
    )
    group.add_argument(
        "--group",
        required=True,
        help="Exact leading/additional main-group name, e.g. TOPQ.",
    )
    group.add_argument(
        "--curation-config",
        type=Path,
        default=default_curation_path(),
        help="Publication policies TOML (default: shared package policy).",
    )
    group.add_argument(
        "--group-title", default="", help="Display title (default: group name)."
    )
    group.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pages/group"),
        help="Destination for group pages, assets and report (default: %(default)s).",
    )
    group.set_defaults(handler=_run_render_group)
    resolve = commands.add_parser(
        "resolve-dois",
        help="Infer DOI citations or retrieve public INSPIRE metadata incrementally.",
        parents=[citations, console],
    )
    inputs = resolve.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--snapshot", type=Path, help="Resolve DOIs found in this registry."
    )
    inputs.add_argument(
        "--doi", action="append", help="DOI or doi.org URL; repeat for multiple DOIs."
    )
    resolve.add_argument(
        "--method",
        choices=("infer", "inspire", "auto"),
        default="infer",
        help="infer: offline JHEP rule; inspire: API only; auto: inference then API (default: %(default)s).",
    )
    resolve.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Revisit inferred/INSPIRE entries; manual citations are never replaced.",
    )
    resolve.add_argument(
        "--limit",
        type=_positive_int,
        help="Maximum number of missing/non-manual entries to attempt.",
    )
    resolve.set_defaults(handler=_run_resolve_dois, validator=_validate_resolution)
    formatting = commands.add_parser(
        "format-citations",
        parents=[citations, console],
        help="Normalise journal abbreviations and starting pages in non-manual citations offline.",
    )
    formatting.set_defaults(handler=_run_format_citations)
    return command


def _run_download_api(args):
    from .downloaders.api import download_registry
    from .downloaders.reporting import run_download

    run_download(
        lambda: download_registry(
            args.output,
            login=args.login,
            allow_count_drop=args.allow_count_drop,
            page_size=args.page_size,
        ),
        kind="API",
        destination=args.output,
        files=[args.output],
        color=args.color,
        validation="Passed: model/schema validation, pagination totals and unique identifiers; "
        + (
            "count-drop guard explicitly overridden"
            if args.allow_count_drop
            else "count-drop guard enabled"
        ),
        recovery_dir=args.output.parent,
        recovery_pattern=f".{args.output.name}.*.tmp",
    )


def _run_refresh(args):
    from .refresh import refresh

    refresh(args, download=_run_download_api, build=_run_build_registry)


def _run_download_html(args):
    from .downloaders.auth import resolve_cookies
    from .downloaders.csv_batch import download_html_csvs
    from .downloaders.html import download_tasks
    from .downloaders.manifest import CSV_REFRESH_MARKER, HTML_MANIFEST
    from .downloaders.reporting import run_download

    tasks = download_tasks()

    def download():
        try:
            import bs4  # noqa: F401

            if args.login:
                import selenium  # noqa: F401
        except ImportError:
            raise ValueError(
                "HTML downloading requires optional dependencies: pip install 'glance-analysis-lister[html]'"
            ) from None
        logger.info(
            "HTML configuration: all accessible records and columns; sequential retrieval; source=%s",
            args.from_html
            if args.from_html is not None
            else "live GLANCE tables (verified TLS)",
        )
        logger.info(
            "Authentication: %s",
            "none (offline HTML replay)"
            if args.from_html is not None
            else "Chrome SSO requested"
            if args.login
            else "using saved cookies",
        )
        cookies = (
            None
            if args.from_html is not None
            else resolve_cookies(args.cookies, generate_new_cookies=args.login)
        )
        return download_html_csvs(
            tasks,
            args.csv_dir,
            args.from_html or args.save_html or Path("debug"),
            cookies=cookies,
            use_local_html=args.from_html is not None,
            debug=args.save_html is not None,
        )

    run_download(
        download,
        kind="HTML",
        destination=args.csv_dir,
        files=[args.csv_dir / task.csv_filename for task in tasks]
        + [args.csv_dir / HTML_MANIFEST],
        validation="Passed: table completeness, headers, row widths and unique identifiers; batch published",
        color=args.color,
        marker=args.csv_dir / CSV_REFRESH_MARKER,
        recovery_dir=args.csv_dir,
        recovery_pattern=".refresh-*",
        saved_html=args.save_html,
    )


def _run_build_registry(args):
    from analysis_lister.registry.builder import build_registry

    result = build_registry(
        args.api_snapshot,
        args.output,
        allow_count_drop=args.allow_count_drop,
        doi_cache=args.doi_cache,
    )
    print_summary(
        "Registry ready", [("Registry", args.output), *result.items()], color=args.color
    )


def _run_compare_snapshots(args):
    from .registry.comparison import compare_files

    report = compare_files(args.before, args.after, output=args.output)
    details = []
    for resource, changes in report["resources"].items():
        counts = changes["counts"]
        details.append(
            (
                resource,
                ", ".join(
                    f"{counts[key]} {key}"
                    for key in ("added", "removed", "changed", "unchanged")
                ),
            )
        )
    if args.output:
        details.append(("Report", args.output))
    print_summary("Snapshot comparison (records only)", details, color=args.color)
    if args.details:
        for resource, changes in report["resources"].items():
            for kind in ("added", "removed"):
                for reference in changes[kind]:
                    print(f"  {kind}: {resource}/{reference}")
            for record in changes["changed"]:
                print(f"  changed: {resource}/{record['reference']}")
                for field in record["fields"]:
                    print(f"    {field['kind']}: {field['path']}")


def _run_render_group(args):
    from analysis_lister.views.build import render_group
    from analysis_lister.views.curation import load_publication_policy
    from analysis_lister.views.profiles import GroupProfile

    counts = render_group(
        args.snapshot,
        args.output_dir,
        GroupProfile(
            args.group,
            args.group_title,
            publication_policy=load_publication_policy(
                args.curation_config, args.group
            ),
        ),
    )
    print_summary(
        "Group views rendered",
        [
            ("Output", args.output_dir),
            ("Report", args.output_dir / "view-report.json"),
            *counts.items(),
        ],
        color=args.color,
    )


def _run_resolve_dois(args):
    from analysis_lister.citations.resolver import resolve_dois, snapshot_dois

    dois = snapshot_dois(args.snapshot) if args.snapshot is not None else args.doi
    summary = resolve_dois(
        dois,
        args.doi_cache,
        method=args.method,
        refresh=args.refresh_existing,
        limit=args.limit,
    )
    print_summary(
        "DOI resolution",
        [(key.capitalize(), value) for key, value in summary.items()]
        + [("Citation store", args.doi_cache)],
        color=args.color,
    )


def _run_format_citations(args):
    from analysis_lister.citations.formatting import format_citations

    changed = format_citations(args.doi_cache)
    print_summary(f"Updated formatting in {changed} citation(s).", color=args.color)


def main(argv=None):
    command = parser()
    args = command.parse_args(
        argv, namespace=argparse.Namespace(verbose=False, quiet=False, color="auto")
    )
    if args.verbose and args.quiet:
        command.error("--verbose cannot be combined with --quiet")
    if args.validator is not None:
        args.validator(command, args)
    with configure_logging(verbose=args.verbose, quiet=args.quiet, color=args.color):
        try:
            args.handler(args)
        except (ValueError, OSError, requests.RequestException) as error:
            logger.error("%s", error)
            logger.debug("Command failed", exc_info=True)
            raise SystemExit(1) from None
