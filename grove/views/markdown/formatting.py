# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Escape source text centrally rather than treating it as Markdown markup."""

from html import escape


def text(value):
    source = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        "<br>"
        if char == "\n"
        else f"&#{ord(char)};"
        if char in "\\`*_{}[]#!|"
        else escape(char, quote=True)
        for char in source
    )
