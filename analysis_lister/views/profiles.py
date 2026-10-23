# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Group identity and presentation options, independent of TOPQ."""

from attrs import frozen


@frozen
class GroupProfile:
    group: str
    title: str = ""

    def __attrs_post_init__(self):
        if not isinstance(self.group, str) or not self.group.strip():
            raise ValueError("Group must be a nonempty name")
        object.__setattr__(self, "group", self.group.strip())
        object.__setattr__(self, "title", self.title.strip() or self.group)
