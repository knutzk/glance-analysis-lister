# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Group presentation and explicit, independent publication curation policy."""

from attrs import frozen


@frozen
class PublicationPolicy:
    title: str = ""
    groups: tuple[str, ...] = ()
    subgroups: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def __attrs_post_init__(self):
        if not isinstance(self.title, str):
            raise ValueError("Publication title must be a string")
        object.__setattr__(self, "title", self.title.strip())
        for field in ("groups", "subgroups", "keywords"):
            values = getattr(self, field)
            if not isinstance(values, (tuple, list)) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"Publication {field} must contain nonempty strings")
            object.__setattr__(
                self, field, tuple(dict.fromkeys(value.strip() for value in values))
            )


@frozen
class GroupProfile:
    group: str
    title: str = ""
    publication_policy: PublicationPolicy | None = None

    def __attrs_post_init__(self):
        if not isinstance(self.group, str) or not self.group.strip():
            raise ValueError("Group must be a nonempty name")
        if not isinstance(self.title, str):
            raise ValueError("Group title must be a string")
        if self.publication_policy is not None and not isinstance(
            self.publication_policy, PublicationPolicy
        ):
            raise ValueError("Publication policy must be a PublicationPolicy or None")
        object.__setattr__(self, "group", self.group.strip())
        object.__setattr__(self, "title", self.title.strip() or self.group)

    @property
    def publication_title(self):
        return (
            self.publication_policy.title if self.publication_policy else ""
        ) or self.title
