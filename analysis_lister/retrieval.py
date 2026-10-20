# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Validated, explicit GLANCE selections independent of display subgroups."""

import json
import re
import tomllib
from importlib.resources import files
from pathlib import Path

from attrs import frozen

SCOPE_FILENAME = "retrieval_scope.json"


@frozen
class RetrievalScope:
    """One GLANCE filter field with any number of alternative values."""

    name: str
    field: str
    operator: str
    values: tuple[int | str, ...]

    def __attrs_post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Retrieval scope requires a nonempty name")
        if not isinstance(self.field, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", self.field
        ):
            raise ValueError("Selection field must be a GLANCE query field name")
        if not isinstance(self.operator, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", self.operator
        ):
            raise ValueError("Selection operator must be a GLANCE query operator name")
        if not isinstance(self.values, (tuple, list)) or not self.values:
            raise ValueError("Selection values must be a nonempty list")
        for value in self.values:
            if not (
                (type(value) is int and value > 0)
                or (isinstance(value, str) and value.strip())
            ):
                raise ValueError(
                    "Selection values must be positive IDs or nonempty strings"
                )
        object.__setattr__(self, "values", tuple(dict.fromkeys(self.values)))

    def query_params(self):
        """Expand alternative values into GLANCE's existing indexed clauses."""
        params = {}
        for index, value in enumerate(self.values):
            params.update(
                {
                    f"c[{index}][i]": index,
                    f"c[{index}][p]": self.field,
                    f"c[{index}][o]": self.operator,
                    f"c[{index}][v]": value,
                }
            )
        return params

    def metadata(self):
        return {
            "name": self.name,
            "selection": {
                "field": self.field,
                "operator": self.operator,
                "values": list(self.values),
            },
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"name", "selection"}:
            raise ValueError("Configuration requires only 'name' and [selection]")
        selection = data["selection"]
        if not isinstance(selection, dict) or set(selection) != {
            "field",
            "operator",
            "values",
        }:
            raise ValueError("Selection requires only field, operator and values")
        return cls(data["name"], **selection)

    def same_selection(self, other):
        return (
            self.field == other.field
            and self.operator == other.operator
            and set(self.values) == set(other.values)
        )


def load_scope(path: Path | None = None) -> RetrievalScope:
    """Load a user TOML file, or the bundled backwards-compatible TOPQ scope."""
    source = path or files("analysis_lister").joinpath("configs/topq.toml")
    return RetrievalScope.from_dict(tomllib.loads(source.read_text(encoding="utf-8")))


def read_scope(directory: Path) -> RetrievalScope | None:
    path = directory / SCOPE_FILENAME
    if not path.exists():
        return None
    return RetrievalScope.from_dict(json.loads(path.read_text(encoding="utf-8")))


def check_scope(scope: RetrievalScope, previous: RetrievalScope | None):
    """Unlabelled legacy datasets are compatible only with the old default."""
    if not scope.same_selection(previous or load_scope()):
        raise ValueError(
            "Retrieval scope differs from the existing dataset. "
            "Use separate CSV and snapshot destinations for a different selection."
        )
