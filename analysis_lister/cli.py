"""Command-line interface for analysis data maintenance and page generation."""

import argparse
import logging
from pathlib import Path

import requests

CSV_DIR = Path("deploy_tools/analysis_lists/csv")
COOKIE_FILE = Path("cookies.json")
SNAPSHOT_PATH = Path("json/glance_registry.json")
OUTPUT_DIR = Path("docs/analyses")


def configure_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    commands = command.add_subparsers(dest="command", required=True)
    for name, description in (
        ("refresh", "Download and publish CSVs and a validated registry."),
        ("download", "Download and publish CSVs only."),
        ("build-registry", "Validate existing CSVs and publish their registry."),
        ("render", "Generate Markdown pages from a registry snapshot."),
        (
            "validate-lookups",
            "Validate lookup dictionaries and optionally review a snapshot.",
        ),
    ):
        sub = commands.add_parser(name, help=description, description=description)
        if name in ("refresh", "download", "build-registry"):
            sub.add_argument(
                "--csv-dir",
                type=Path,
                default=CSV_DIR,
                help="CSV directory (default: %(default)s).",
            )
        if name != "download":
            sub.add_argument(
                "--snapshot",
                type=Path,
                default=None if name == "validate-lookups" else SNAPSHOT_PATH,
                help="Registry JSON path; for validate-lookups, enables snapshot review.",
            )
        if name in ("refresh", "build-registry"):
            sub.add_argument(
                "--allow-count-drop",
                action="store_true",
                help="Allow an understood drop in registry counts; other checks still apply.",
            )
        if name in ("refresh", "download"):
            source = sub.add_mutually_exclusive_group()
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
            sub.add_argument(
                "--save-html",
                type=Path,
                metavar="DIR",
                help="Save downloaded HTML tables to DIR.",
            )
            sub.add_argument(
                "--cookies",
                type=Path,
                default=COOKIE_FILE,
                help="Session cookie file (default: %(default)s).",
            )
        if name == "render":
            sub.add_argument(
                "--output-dir",
                type=Path,
                default=OUTPUT_DIR,
                help="Markdown destination (default: %(default)s).",
            )
    return command


def run(args):
    """Dispatch a parsed command; import optional download code only when needed."""
    if args.command in ("refresh", "download"):
        from analysis_lister.download import download_options, download_tasks
        from analysis_lister.refresh import refresh_analysis_lists, refresh_csv_files

        options = download_options(
            args.cookies,
            use_local_html=args.from_html is not None,
            generate_new_cookies=args.login,
            debug=args.save_html is not None,
        )
        html_dir = args.from_html or args.save_html or Path("debug")
        if args.command == "refresh":
            refresh_analysis_lists(
                args.csv_dir,
                html_dir,
                args.snapshot,
                force=args.allow_count_drop,
                **options,
            )
        else:
            refresh_csv_files(
                download_tasks(args.csv_dir), args.csv_dir, html_dir, **options
            )
    elif args.command == "build-registry":
        from analysis_lister.refresh import update_registry

        update_registry(args.csv_dir, args.snapshot, force=args.allow_count_drop)
    elif args.command == "render":
        from analysis_lister.render import render_pages

        render_pages(args.snapshot, args.output_dir)
    else:
        from analysis_lister.lookup_dicts.validation import validate_lookups

        validate_lookups()
        if args.snapshot is not None:
            from analysis_lister.glance.glance_registry import GlanceRegistry
            from analysis_lister.lookup_dicts.review import lookup_review_notices

            notices = lookup_review_notices(GlanceRegistry.from_json(args.snapshot))
            for level, message in notices:
                print(f"{logging.getLevelName(level)}: {message}")
            print(f"Snapshot review: {len(notices)} notice(s); no entries changed.")
        print("All analysis lookup dictionaries are valid.")


def main(argv=None):
    command = parser()
    args = command.parse_args(argv)
    if (
        args.command in ("refresh", "download")
        and args.from_html is not None
        and args.save_html is not None
    ):
        command.error("--from-html cannot be combined with --save-html")
    configure_logging()
    try:
        run(args)
    except (ValueError, OSError, requests.RequestException) as error:
        raise SystemExit(str(error)) from None
