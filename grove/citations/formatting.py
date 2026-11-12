# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Citation formatting: isolated concerns with no registry model dependency."""

import re
from pathlib import Path

from .store import load_store, save_store

JOURNAL_NAMES = {
    "phys.lett.b": "Phys. Lett. B",
    "phys.rev.c": "Phys. Rev. C",
    "phys.rev.d": "Phys. Rev. D",
    "phys.rev.lett.": "Phys. Rev. Lett.",
    "phys.rept.": "Phys. Rep.",
    "phys.rep.": "Phys. Rep.",
    "rept.prog.phys.": "Rep. Prog. Phys.",
    "rep.prog.phys.": "Rep. Prog. Phys.",
    "eur.phys.j.c": "Eur. Phys. J. C",
    "comput.softw.bigsci.": "Comput. Softw. Big Sci.",
    "sci.bull.": "Sci. Bull.",
    "newj.phys.": "New J. Phys.",
    "chin.phys.c": "Chin. Phys. C",
    "naturephys.": "Nature Phys.",
    "naturecommun.": "Nature Commun.",
    "eur.phys.j.plus": "Eur. Phys. J. Plus",
    "mach.learn.sci.tech.": "Mach. Learn. Sci. Tech.",
}


def format_journal_name(journal):
    """Normalise known abbreviations without guessing punctuation for others."""
    key = re.sub(r"\s+", "", journal).casefold()
    return JOURNAL_NAMES.get(key, " ".join(journal.split()))


def starting_page(locator):
    """Shorten conventional numeric or letter-prefixed page ranges."""
    match = re.fullmatch(
        r"(?P<prefix>[A-Za-z]*)(?P<start>\d+)\s*[-–—]\s*"
        r"(?P<end_prefix>[A-Za-z]*)(?P<end>\d+)",
        locator,
    )
    if (
        match
        and match["end_prefix"] in ("", match["prefix"])
        and int(match["end"]) >= int(match["start"])
    ):
        return match["prefix"] + match["start"]
    return locator


def format_citations(path: Path):
    """Apply journal typography offline, retaining manual entries and provenance."""
    entries = load_store(path)
    changed = 0
    pattern = re.compile(
        r"(?P<prefix>(?:Erratum|Addendum|Editorial note): )?"
        r"(?P<journal>.+?) (?P<volume>\S+) \((?P<year>\d{4})\) (?P<locator>.+)",
    )
    for entry in entries.values():
        if entry["source"] == "manual":
            continue
        match = pattern.fullmatch(entry["citation"])
        if match is None:
            continue
        citation = (
            (match["prefix"] or "")
            + format_journal_name(match["journal"])
            + f" {match['volume']} ({match['year']}) "
            + starting_page(match["locator"])
        )
        if citation != entry["citation"]:
            entry["citation"] = citation
            changed += 1
    if changed:
        save_store(path, entries)
    return changed
