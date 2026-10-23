# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Command-line interface for analysis data maintenance and page generation."""

import argparse
import logging
from pathlib import Path

import requests

from .console import configure_logging, print_summary
from .views.curation import default_curation_path

logger = logging.getLogger(__name__)

SUPPLEMENT_CSV_DIR = Path("csv/supplemental")
API_SNAPSHOT_PATH = Path("json/glance_api_registry.json")
CURATED_SNAPSHOT_PATH = Path("json/glance_curated_registry.json")
COOKIE_FILE = Path("cookies.json")


def _validate_download(command, args):
    if args.from_html is not None and args.save_html is not None:
        command.error("--from-html cannot be combined with --save-html")


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
        default=Path("json/doi_metadata.json"),
        help="Persistent citation JSON dictionary (default: %(default)s); read offline if present.",
    )
    supplement_csv = argparse.ArgumentParser(add_help=False)
    supplement_csv.add_argument(
        "--csv-dir",
        type=Path,
        default=SUPPLEMENT_CSV_DIR,
        help="Supplemental CSV directory (default: %(default)s).",
    )

    counts = argparse.ArgumentParser(add_help=False)
    counts.add_argument(
        "--allow-count-drop",
        action="store_true",
        help="Allow an understood drop in registry counts; other checks still apply.",
    )

    download = argparse.ArgumentParser(add_help=False)
    source = download.add_mutually_exclusive_group()
    source.add_argument(
        "--login",
        action="store_true",
        help="Log in using Chrome and save fresh cookies.",
    )
    source.add_argument(
        "--from-html",
        type=Path,
        metavar="DIR",
        help="Read saved HTML tables from DIR without network access.",
    )
    download.add_argument(
        "--save-html",
        type=Path,
        metavar="DIR",
        help="Save downloaded HTML tables to DIR.",
    )
    download.add_argument(
        "--cookies",
        type=Path,
        default=COOKIE_FILE,
        help="Session cookie file (default: %(default)s).",
    )
    download.set_defaults(validator=_validate_download)

    command = argparse.ArgumentParser(description=__doc__, parents=[console])
    command.set_defaults(validator=None)
    commands = command.add_subparsers(dest="command", required=True)
    api = commands.add_parser(
        "download-api",
        help="Download a separate, rich API source registry using browser SSO.",
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
    api.set_defaults(handler=_run_download_api)
    for name, description, parents, handler in (
        (
            "download-html",
            "Download supplemental CSVs using Selenium SSO.",
            [supplement_csv, download],
            _run_download,
        ),
        (
            "build-registry",
            "Build a curated registry from API JSON and supplemental CSVs.",
            [supplement_csv, counts],
            _run_build_registry,
        ),
    ):
        sub = commands.add_parser(
            name,
            help=description,
            description=description,
            parents=[*parents, console]
            if name == "download-html"
            else [*parents, citations, console],
        )
        sub.set_defaults(handler=handler)
        if name == "build-registry":
            sub.add_argument(
                "--api-snapshot",
                type=Path,
                default=API_SNAPSHOT_PATH,
                help="API JSON input (default: %(default)s).",
            )
            sub.add_argument(
                "--output",
                type=Path,
                default=CURATED_SNAPSHOT_PATH,
                help="Curated JSON output (default: %(default)s).",
            )
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
        help="Maximum number of missing/unlocked entries to attempt.",
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
    from analysis_lister.downloaders.api import download_registry

    counts = download_registry(
        args.output, login=args.login, allow_count_drop=args.allow_count_drop
    )
    print_summary(
        "API registry downloaded",
        [("Registry", args.output), *counts.items()],
        color=args.color,
    )


def _download_cookies(args):
    from analysis_lister.downloaders.auth import resolve_cookies

    if args.from_html is not None:
        return None
    return resolve_cookies(args.cookies, generate_new_cookies=args.login)


def _run_download(args):
    from analysis_lister.downloaders.csv_batch import download_html_csvs
    from analysis_lister.downloaders.html import download_tasks

    download_html_csvs(
        download_tasks(),
        args.csv_dir,
        args.from_html or args.save_html or Path("debug"),
        cookies=_download_cookies(args),
        use_local_html=args.from_html is not None,
        debug=args.save_html is not None,
    )
    print_summary(
        "Download complete", [("CSV directory", args.csv_dir)], color=args.color
    )


def _run_build_registry(args):
    from analysis_lister.registry.builder import build_registry

    result = build_registry(
        args.api_snapshot,
        args.csv_dir,
        args.output,
        allow_count_drop=args.allow_count_drop,
        doi_cache=args.doi_cache,
    )
    print_summary(
        "Registry ready", [("Registry", args.output), *result.items()], color=args.color
    )


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


def run(args):
    """Invoke the registered handler; optional dependencies remain lazy imports."""
    if args.command == "build-registry" or not hasattr(args, "doi_cache"):
        args.handler(args)
        return
    from analysis_lister.citations.store import cached_citations

    with cached_citations(args.doi_cache):
        args.handler(args)


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
            run(args)
        except (ValueError, OSError, requests.RequestException) as error:
            logger.error("%s", error)
            logger.debug("Command failed", exc_info=True)
            raise SystemExit(1) from None
