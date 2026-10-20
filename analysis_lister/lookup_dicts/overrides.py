"""Apply validated local lookup dictionaries without executing their source."""

from contextlib import contextmanager
from importlib import import_module

from .validation import TABLES, _read_table, validate_lookups


@contextmanager
def local_lookups(directory):
    """Temporarily replace shared dictionaries; restore them after failure."""
    if directory is None:
        yield
        return

    validate_lookups(directory)
    errors = []
    tables = {
        table: _read_table(directory / filename, table, errors)
        for filename, table in TABLES.items()
    }
    if errors:
        raise ValueError("Invalid local lookup dictionaries:\n" + "\n".join(errors))

    originals = []
    try:
        for filename, table in TABLES.items():
            module = import_module(f"analysis_lister.lookup_dicts.{filename[:-3]}")
            target = getattr(module, table)
            originals.append((target, target.copy()))
            target.clear()
            target.update({key: value for key, (value, _) in tables[table].items()})
        yield
    finally:
        for target, original in originals:
            target.clear()
            target.update(original)
