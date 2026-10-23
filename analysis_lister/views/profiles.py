# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Group identity and presentation options, independent of TOPQ."""

from attrs import frozen


@frozen
class GroupProfile:
    group: str
    title: str = ""
    recent_limit: int = 10
    archive_keywords: tuple[str, ...] = ()
    archive_groups: tuple[str, ...] | None = None
    archive_title: str = ""
    archive_subgroups: tuple[str, ...] = ()

    def __attrs_post_init__(self):
        if not isinstance(self.group, str) or not self.group.strip():
            raise ValueError("Group must be a nonempty name")
        if type(self.recent_limit) is not int or self.recent_limit < 1:
            raise ValueError("Recent publication limit must be positive")
        for field in (
            "archive_keywords",
            "archive_groups",
            "archive_subgroups",
        ):
            values = getattr(self, field)
            if field == "archive_groups" and values is None:
                continue
            if isinstance(values, str) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"{field} must contain nonempty strings")
            object.__setattr__(
                self, field, tuple(dict.fromkeys(value.strip() for value in values))
            )
        if not isinstance(self.archive_title, str):
            raise ValueError("Archive title must be a string")
        object.__setattr__(self, "archive_title", self.archive_title.strip())
        object.__setattr__(self, "group", self.group.strip())
        object.__setattr__(self, "title", self.title.strip() or self.group)
