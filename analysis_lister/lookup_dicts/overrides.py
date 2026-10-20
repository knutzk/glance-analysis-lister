# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Apply validated local lookup dictionaries without executing their source."""

from contextlib import contextmanager
from contextvars import ContextVar
from importlib import import_module

from .validation import _read_table, lookup_tables, validate_lookups

_PRIVATE_JOURNALS = ContextVar("private_journal_overrides", default=None)


def private_journal_overrides():
    return _PRIVATE_JOURNALS.get() or {}


@contextmanager
def local_lookups(directory):
    """Temporarily replace shared dictionaries; restore them after failure."""
    if directory is None:
        yield
        return

    validate_lookups(directory)
    definitions = lookup_tables(directory)
    errors = []
    tables = {
        table: _read_table(directory / filename, table, errors)
        for filename, table in definitions.items()
    }
    if errors:
        raise ValueError("Invalid local lookup dictionaries:\n" + "\n".join(errors))

    originals = []
    token = _PRIVATE_JOURNALS.set(
        {key: value for key, (value, _) in tables.get("JournalRefs", {}).items()}
    )
    try:
        for filename, table in definitions.items():
            module = import_module(f"analysis_lister.lookup_dicts.{filename[:-3]}")
            target = getattr(module, table)
            originals.append((target, target.copy()))
            target.clear()
            target.update({key: value for key, (value, _) in tables[table].items()})
        yield
    finally:
        _PRIVATE_JOURNALS.reset(token)
        for target, original in originals:
            target.clear()
            target.update(original)
