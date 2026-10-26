# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Readable CLI output without changing logging configuration on import."""

import logging
import os
import shutil
import sys
import textwrap
from contextlib import contextmanager


def use_color(stream, mode="auto"):
    if mode != "auto":
        return mode == "always"
    return (
        "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
        and bool(getattr(stream, "isatty", lambda: False)())
    )


def _wrap(message, width):
    """Wrap prose while keeping grouped diagnostic bullets aligned."""
    lines = []
    for line in message.splitlines() or [""]:
        indent = line[: len(line) - len(line.lstrip())]
        bullet = "- " if line.lstrip().startswith("- ") else ""
        lines.extend(
            textwrap.wrap(
                line.strip()[len(bullet) :],
                width=max(width, 20),
                initial_indent=indent + bullet,
                subsequent_indent=indent + ("  " if bullet else ""),
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )
    return lines


class ConsoleFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "90",
        logging.INFO: "36",
        logging.WARNING: "33",
        logging.ERROR: "31",
        logging.CRITICAL: "31;1",
    }

    def __init__(self, *, color=False, verbose=False, width=100):
        super().__init__()
        self.color = color
        self.verbose = verbose
        self.width = width

    def format(self, record):
        label = "WARN" if record.levelno == logging.WARNING else record.levelname
        plain = f"{label:<5} "
        prefix = plain
        if self.color:
            prefix = f"\033[{self.COLORS.get(record.levelno, '0')}m{label:<5}\033[0m "
        message = record.getMessage()
        if self.verbose:
            stamp = self.formatTime(record, "%H:%M:%S")
            plain = f"{stamp} {plain}"
            prefix = f"{stamp} {prefix}"
            message = f"{record.name.removeprefix('analysis_lister.')}: {message}"
        lines = _wrap(message, self.width - len(plain))
        result = prefix + ("\n" + " " * len(plain)).join(lines)
        if record.exc_info:
            result += "\n" + self.formatException(record.exc_info)
        return result


@contextmanager
def configure_logging(*, verbose=False, quiet=False, color="auto"):
    """Own a handler for this CLI invocation; preserve host/root logging."""
    logger = logging.getLogger("analysis_lister")
    previous_level = logger.level
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        ConsoleFormatter(
            color=use_color(sys.stderr, color),
            verbose=verbose,
            width=shutil.get_terminal_size((100, 24)).columns,
        )
    )
    logger.setLevel(
        logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    )
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(previous_level)


def print_summary(title, details=(), *, color="auto"):
    """Write command results to stdout, independently of diagnostic verbosity."""
    if use_color(sys.stdout, color):
        print(f"\033[1;32m{title}\033[0m")
    else:
        print(title)
    details = list(details)
    padding = max((len(str(label)) for label, _ in details), default=0)
    for label, value in details:
        if type(value) is int:
            value = f"{value:,}"
        print(f"  {str(label):<{padding}}  {value}")
    sys.stdout.flush()
