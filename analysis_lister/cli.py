"""Shared command-line defaults and presentation helpers."""

import logging
from contextlib import contextmanager
from pathlib import Path

import requests

CSV_DIR = Path("deploy_tools/analysis_lists/csv")
DEBUG_DIR = Path("debug")
COOKIE_FILE = Path("cookies.json")
SNAPSHOT_PATH = Path("json/glance_registry.json")


def configure_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


@contextmanager
def command_errors():
    """Translate expected workflow failures into a nonzero CLI exit."""
    try:
        yield
    except (ValueError, OSError, requests.RequestException) as error:
        raise SystemExit(str(error)) from error


def add_download_arguments(parser):
    """Share download options with the combined refresh command."""
    parser.add_argument(
        "--generate-new-cookies",
        action="store_true",
        help="Generate new cookies using Selenium.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save raw HTML tables to debug directory.",
    )
    parser.add_argument(
        "--use-local-html",
        action="store_true",
        help="Read HTML from debug directory instead of fetching it.",
    )
