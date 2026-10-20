# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Collect lookup notices within one command, without suppressing other logs."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)
_model_diagnostics_enabled = ContextVar("model_diagnostics_enabled", default=True)
_notices: ContextVar[dict | None] = ContextVar("lookup_notices", default=None)


def model_diagnostic(source_logger, level, message, *args):
    """Report model inconsistencies except while reading a comparison baseline."""
    if _model_diagnostics_enabled.get():
        source_logger.log(level, message, *args)


def lookup_notice(source_logger, level, message, *args):
    """Log immediately outside a report; otherwise retain each unique notice."""
    notices = _notices.get()
    if notices is None:
        source_logger.log(level, message, *args)
    else:
        text = message % args if args else message
        notices[(level, text)] = None


@contextmanager
def lookup_report():
    """Emit a grouped report on exit, also if work fails; nested scopes share it."""
    if _notices.get() is not None:
        yield
        return
    notices = {}
    token = _notices.set(notices)
    try:
        yield
    finally:
        _notices.reset(token)
        for level in sorted({level for level, _ in notices}):
            messages = sorted(
                message for severity, message in notices if severity == level
            )
            logger.log(
                level,
                "%d %s notice(s):\n%s",
                len(messages),
                logging.getLevelName(level).lower(),
                "\n".join(f"  - {message}" for message in messages),
            )


@contextmanager
def discard_baseline_notices():
    """Ignore lookup and model notices from a comparison-only baseline.

    Parsing, validation and exceptions still run. Candidate models and normal
    snapshot loading continue to report their inconsistencies.
    """
    token = _notices.set({})
    model_token = _model_diagnostics_enabled.set(False)
    try:
        yield
    finally:
        _notices.reset(token)
        _model_diagnostics_enabled.reset(model_token)
