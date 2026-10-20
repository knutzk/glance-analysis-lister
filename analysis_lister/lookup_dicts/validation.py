# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Validate maintained lookup source before duplicate keys can be hidden."""

import ast
import re
from pathlib import Path

from ..citation_store import citation_problem, default_store_path, load_store

TABLES = {
    "short_titles.py": "ShortTitles",
    "known_duplicates.py": "KnownDuplicates",
    "doi_order.py": "DoiOrder",
}
REF_CODE = re.compile(r"[A-Z][A-Z0-9]+-\d{4}-\d+")
DOI = re.compile(r"10\.\d{4,9}/\S+")


def lookup_tables(directory):
    """Private directories may still supply the optional legacy citation table."""
    tables = TABLES.copy()
    if (directory / "journal_refs.py").is_file():
        tables["journal_refs.py"] = "JournalRefs"
    if (directory / "clones.py").is_file():
        tables["clones.py"] = "Clones"
    return tables


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _has_provenance(lines, key_line):
    """Require a reason or source in the comment block immediately above a key."""
    for line in reversed(lines[: key_line - 1]):
        text = line.strip()
        if not text.startswith("#"):
            break
        if re.match(r"#\s*(Reason|Source):\s*\S", text):
            return True
    return False


def _value_error(table, value):
    if table == "JournalRefs":
        return citation_problem(value)
    if table in {"KnownDuplicates", "Clones"}:
        return (
            None if _matches(REF_CODE, value) else "expected an analysis reference code"
        )
    if table == "DoiOrder":
        if not isinstance(value, list) or not value:
            return "expected a nonempty list of bare DOI strings"
        if any(not _matches(DOI, doi) for doi in value):
            return "expected bare DOI strings in the order list"
        if len(value) != len(set(value)):
            return "DOI order contains repeated DOIs"
        return None
    if not isinstance(value, str) or not value.strip():
        return "expected a nonempty string"
    return None


def _read_table(path, table, errors):
    """Read literal entries separately, retaining duplicate keys and line numbers."""
    try:
        source = path.read_text(encoding="utf8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        errors.append(f"{path}: {exc}")
        return {}

    definitions = []
    for node in tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        if (
            len(targets) == 1
            and isinstance(targets[0], ast.Name)
            and targets[0].id == table
        ):
            definitions.append(node)
        else:
            errors.append(
                f"{path}:{node.lineno}: keep {table} as a single literal dictionary; unsupported statement"
            )
    if len(definitions) != 1 or not isinstance(definitions[0].value, ast.Dict):
        errors.append(f"{path}: expected exactly one literal dictionary named {table}")
        return {}

    entries = {}
    first_lines = {}
    for key_node, value_node in zip(
        definitions[0].value.keys, definitions[0].value.values, strict=True
    ):
        line = value_node.lineno if key_node is None else key_node.lineno
        location = f"{path}:{line}"
        try:
            key = ast.literal_eval(key_node)
            value = ast.literal_eval(value_node)
        except (ValueError, TypeError, SyntaxError):
            errors.append(f"{location}: lookup keys and values must be literals")
            continue
        pattern = DOI if table == "JournalRefs" else REF_CODE
        if not _matches(pattern, key):
            errors.append(f"{location}: invalid {table} key {key!r}")
            continue
        identity = key.lower() if table == "JournalRefs" else key
        if identity in first_lines:
            errors.append(
                f"{location}: duplicate key {key!r}; first defined on line {first_lines[identity]}"
            )
        first_lines.setdefault(identity, line)
        if table == "JournalRefs" and isinstance(value_node, ast.Dict):
            field_names = [ast.literal_eval(field) for field in value_node.keys]
            repeated = sorted(
                {repr(name) for name in field_names if field_names.count(name) > 1}
            )
            if repeated:
                errors.append(
                    f"{location}: {key}: duplicate citation fields {repeated}"
                )
        if table in {"KnownDuplicates", "DoiOrder", "Clones"} and not _has_provenance(
            source.splitlines(), line
        ):
            errors.append(
                f"{location}: {key}: add a # Reason: or # Source: comment "
                "immediately above this factual override"
            )
        problem = _value_error(table, value)
        if problem:
            errors.append(f"{location}: {key}: {problem}")
        else:
            entries[key] = (value, line)
    return entries


def validate_lookups(directory: Path | None = None):
    """Raise one diagnostic report for invalid lookup definitions.

    Historical entries need not belong to today's snapshot. DOI overrides are
    additionally checked against actual paper DOIs when each Paper is loaded.
    """
    if directory is None:
        directory = Path(__file__).resolve().parent
        definitions = TABLES | {"clones.py": "Clones"}
        load_store(default_store_path())
    else:
        definitions = lookup_tables(directory)
    errors = []
    tables = {
        table: _read_table(directory / filename, table, errors)
        for filename, table in definitions.items()
    }
    for table, filename, label in (
        ("KnownDuplicates", "known_duplicates.py", "duplicate mapping"),
        ("Clones", "clones.py", "clone mapping"),
    ):
        mappings = tables.get(table, {})
        reported = set()
        for start in mappings:
            trail = []
            current = start
            while current in mappings:
                if current in trail:
                    cycle = trail[trail.index(current) :]
                    identity = frozenset(cycle)
                    if identity not in reported:
                        reported.add(identity)
                        line = mappings[current][1]
                        errors.append(
                            f"{directory / filename}:{line}: {label} cycle: "
                            + " -> ".join([*cycle, current])
                        )
                    break
                trail.append(current)
                current = mappings[current][0]
    if errors:
        raise ValueError("Invalid analysis lookup dictionaries:\n" + "\n".join(errors))
