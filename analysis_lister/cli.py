# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Command-line interface for analysis data maintenance and page generation."""

import argparse
import logging
from pathlib import Path

import requests

from .console import configure_logging, print_summary

logger = logging.getLogger(__name__)

CSV_DIR = Path("csv")
COOKIE_FILE = Path("cookies.json")
SNAPSHOT_PATH = Path("json/glance_registry.json")
OUTPUT_DIR = Path("pages")


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
    csv = argparse.ArgumentParser(add_help=False)
    csv.add_argument(
        "--csv-dir",
        type=Path,
        default=CSV_DIR,
        help="CSV directory (default: %(default)s).",
    )

    snapshot = argparse.ArgumentParser(add_help=False)
    snapshot.add_argument(
        "--snapshot",
        type=Path,
        default=SNAPSHOT_PATH,
        help="Registry JSON path (default: %(default)s).",
    )

    counts = argparse.ArgumentParser(add_help=False)
    counts.add_argument(
        "--allow-count-drop",
        action="store_true",
        help="Allow an understood drop in registry counts; other checks still apply.",
    )

    download = argparse.ArgumentParser(add_help=False)
    download.add_argument(
        "--config",
        type=Path,
        help="Retrieval TOML configuration (default: all accessible ATLAS records).",
    )
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

    output = argparse.ArgumentParser(add_help=False)
    output.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Markdown destination (default: %(default)s).",
    )

    obsidian_output = argparse.ArgumentParser(add_help=False)
    obsidian_output.add_argument(
        "--output-dir",
        type=Path,
        default=Path("obsidian_output"),
        help="Obsidian destination (default: %(default)s).",
    )

    review = argparse.ArgumentParser(add_help=False)
    review.add_argument(
        "--snapshot",
        type=Path,
        help="Review lookup use against this registry JSON snapshot.",
    )

    command = argparse.ArgumentParser(description=__doc__, parents=[console])
    command.set_defaults(validator=None)
    commands = command.add_subparsers(dest="command", required=True)
    for name, description, parents, handler in (
        (
            "refresh",
            "Download and publish CSVs and a validated registry.",
            [csv, snapshot, counts, download],
            _run_refresh,
        ),
        ("download", "Download and publish CSVs only.", [csv, download], _run_download),
        (
            "build-registry",
            "Validate existing CSVs and publish their registry.",
            [csv, snapshot, counts],
            _run_build_registry,
        ),
        (
            "render",
            "Generate Markdown pages from a registry snapshot.",
            [snapshot, output],
            _run_render,
        ),
        (
            "validate-lookups",
            "Validate lookup dictionaries and optionally review a snapshot.",
            [review],
            _run_validate_lookups,
        ),
        (
            "export-obsidian",
            "Export papers and ongoing analyses as Obsidian notes.",
            [snapshot, obsidian_output],
            _run_export_obsidian,
        ),
    ):
        sub = commands.add_parser(
            name,
            help=description,
            description=description,
            parents=[*parents, citations, console],
        )
        sub.set_defaults(handler=handler)
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
    api = commands.add_parser(
        "download-api",
        help="Download a separate, rich API source registry using browser SSO.",
        parents=[citations, console, counts],
    )
    api.add_argument(
        "--output", type=Path, required=True, help="API source JSON destination."
    )
    api.add_argument(
        "--login", action="store_true", help="Open CERN SSO in your browser."
    )
    api.set_defaults(handler=_run_download_api)
    return command


def _run_download_api(args):
    from analysis_lister.api import download_registry

    counts = download_registry(
        args.output, login=args.login, allow_count_drop=args.allow_count_drop
    )
    print_summary(
        "API registry downloaded",
        [("Registry", args.output), *counts.items()],
        color=args.color,
    )


def _download_cookies(args):
    from analysis_lister.download import resolve_cookies

    if args.from_html is not None:
        return None
    return resolve_cookies(args.cookies, generate_new_cookies=args.login)


def _retrieval_options(args):
    from analysis_lister.retrieval import load_scope

    return {"scope": load_scope(args.config)} if args.config is not None else {}


def _run_refresh(args):
    from analysis_lister.refresh import refresh_analysis_lists

    options = _retrieval_options(args)
    refresh_analysis_lists(
        args.csv_dir,
        args.from_html or args.save_html or Path("debug"),
        args.snapshot,
        force=args.allow_count_drop,
        cookies=_download_cookies(args),
        use_local_html=args.from_html is not None,
        debug=args.save_html is not None,
        **options,
    )
    print_summary(
        "Refresh complete",
        [("CSV directory", args.csv_dir), ("Registry", args.snapshot)],
        color=args.color,
    )


def _run_download(args):
    from analysis_lister.download import download_tasks
    from analysis_lister.refresh import refresh_csv_files

    options = _retrieval_options(args)
    refresh_csv_files(
        download_tasks(),
        args.csv_dir,
        args.from_html or args.save_html or Path("debug"),
        cookies=_download_cookies(args),
        use_local_html=args.from_html is not None,
        debug=args.save_html is not None,
        **options,
    )
    print_summary(
        "Download complete", [("CSV directory", args.csv_dir)], color=args.color
    )


def _run_build_registry(args):
    from analysis_lister.refresh import update_registry

    update_registry(args.csv_dir, args.snapshot, force=args.allow_count_drop)
    print_summary("Registry ready", [("Registry", args.snapshot)], color=args.color)


def _run_render(args):
    from analysis_lister.render import render_pages

    render_pages(args.snapshot, args.output_dir)
    print_summary("Pages rendered", [("Output", args.output_dir)], color=args.color)


def _run_export_obsidian(args):
    from analysis_lister.obsidian import export_obsidian

    export_obsidian(args.snapshot, args.output_dir)
    print_summary(
        "Obsidian export complete", [("Output", args.output_dir)], color=args.color
    )


def _run_validate_lookups(args):
    from analysis_lister.lookup_validation import validate_lookups

    validate_lookups()
    if args.snapshot is not None:
        from analysis_lister.glance.glance_registry import GlanceRegistry
        from analysis_lister.lookup_review import lookup_review_notices

        notices = lookup_review_notices(GlanceRegistry.from_json(args.snapshot))
        for level, message in notices:
            logger.log(level, "%s", message)
        print(f"Snapshot review: {len(notices)} notice(s); no entries changed.")
    print_summary("All analysis lookup dictionaries are valid.", color=args.color)


def _run_resolve_dois(args):
    from analysis_lister.doi_resolver import resolve_dois, snapshot_dois

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
    from analysis_lister.doi_resolver import format_citations

    changed = format_citations(args.doi_cache)
    print_summary(f"Updated formatting in {changed} citation(s).", color=args.color)


def run(args):
    """Invoke the registered handler; optional dependencies remain lazy imports."""
    from analysis_lister.citation_store import cached_citations

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
