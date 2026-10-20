# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Module that outputs Markdown files for use in Obsidian."""

import json
import logging
import re
import unicodedata
from pathlib import Path

from analysis_lister.diagnostics import lookup_report
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.markdown.subgroup_pages.ongoing import render_analysis_block
from analysis_lister.markdown.subgroup_pages.published import render_paper_block

logger = logging.getLogger(__name__)


def tagify_string(value):
    """Converts a string into a tag-friendly format.

    Performing the following transformations:
    - Replaces Greek letters 'γ' with 'y' and 'τ' with 't'.
    - Normalizes the string to NFKD form and removes any non-ASCII characters.
    - Removes any non-word characters except for whitespace and hyphens.
    - Replaces sequences of whitespace and hyphens with a single hyphen.
    - Strips leading and trailing hyphens and underscores.

    Args:
        value (str): The input string to be transformed.

    Returns:
        str: The transformed, tag-friendly string.

    """
    value = value.replace("γ", "y").replace("τ", "t")
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value)
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def note_date(entry, entry_type: str) -> str:
    """Return the date an Obsidian note is sorted by.

    Args:
        entry: The Analysis or Paper instance the note describes.
        entry_type: Either "paper" or "analysis".

    Returns:
        The publication date of a paper, falling back to its submission
        date, or the start date of an analysis.

    """
    if entry_type == "analysis":
        return entry.date_start

    return entry.date_publication or entry.date_submission


def render_front_matter(entry, filename: str, entry_type: str) -> str:
    """Return the YAML front matter of one Obsidian note.

    Args:
        entry: The Analysis or Paper instance the note describes.
        filename: Name of the note, which doubles as its Obsidian tag.
        entry_type: Either "paper" or "analysis".

    Returns:
        str object with the front matter, delimiters included.

    """
    title = entry.ref_code
    if entry.title_short:
        title += f" – {entry.title_short}"

    lines = [
        "---",
        "tags:",
        "  - TopPlusX",
        f"  - {filename}",
        f"glance-id: {entry.ref_code}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "summary: "
        + json.dumps(
            entry.title_short_public if entry_type == "paper" else entry.title_short,
            ensure_ascii=False,
        ),
    ]

    date = note_date(entry, entry_type)
    if date:
        lines.append(f"date: {date}")

    return "\n".join(lines + ["---"])


def write_markdown_file(entry, directory: Path, filename: str, entry_type: str):
    """Generalized function to write Markdown files for papers and analyses."""
    logger.debug(f"Writing {entry_type} file: {filename}.md")
    with open(directory / f"{filename}.md", "w", encoding="utf8") as f:
        f.write(
            f"""{render_front_matter(entry, filename, entry_type)}

{render_paper_block(entry, attribute_tag=False, heading_level=1) if entry_type == "paper" else render_analysis_block(entry, attribute_tag=False, heading_level=1)}

## Relevant meetings

```dataview
TABLE date as Date, summary as Summary
FROM "meeting-notes" and #{filename}
SORT date desc
```

## Document reviews

```dataview
TABLE date as Date, doc-type+" v"+doc-version as "Reviewed version"
FROM "document-reviews" and #{filename}
SORT date desc
```

"""
        )
    logger.debug(f"Successfully wrote {entry_type} file: {filename}.md")


def generate_filename(entry):
    """Generate a filename from the reference code and GLANCE short title."""
    suffix = tagify_string(entry.title_short)
    return entry.ref_code + ("-" + suffix if suffix else "")


def warn_about_stale_notes(directory: Path, written: set):
    """Report notes in an output directory that this run did not write.

    The name of a note carries its GLANCE short title, so changing that title
    leaves the note under the old name behind, and entries
    that drop out of the registry keep their note as well. Neither is removed
    here: the directory may be part of a vault, so the deleting is left to
    whoever knows what else lives in it.

    Args:
        directory: Output directory to check.
        written: Names of the files this run has written.

    """
    stale = sorted(p.name for p in directory.glob("*.md") if p.name not in written)
    if not stale:
        return

    logger.warning(
        "%d notes in %s were not written by this run and may be outdated:\n%s",
        len(stale),
        directory,
        "\n".join(f"  - {name}" for name in stale),
    )


@lookup_report()
def export_obsidian(snapshot_path: Path, output_dir: Path):
    """Export papers and ongoing analyses; report stale notes without deleting them."""
    logger.debug("Loading papers and analyses data.")
    registry = GlanceRegistry.from_json(snapshot_path)

    logger.info(
        "Exporting %s paper notes and %s ongoing analysis notes",
        f"{len(registry.papers):,}",
        f"{len(registry.analyses):,}",
    )

    # Ensure output directories exist.
    logger.debug(f"Creating output directories if they do not exist: {output_dir}")
    published_dir = output_dir / "obs_published"
    ongoing_dir = output_dir / "obs_ongoing"
    published_dir.mkdir(parents=True, exist_ok=True)
    ongoing_dir.mkdir(parents=True, exist_ok=True)

    logger.debug("Generating Markdown files for published papers.")
    written_papers = set()
    for p in registry.papers:
        filename = generate_filename(p)
        write_markdown_file(
            entry=p, directory=published_dir, filename=filename, entry_type="paper"
        )
        written_papers.add(f"{filename}.md")

    logger.debug("Generating Markdown files for ongoing analyses.")
    written_analyses = set()
    for a in registry.analyses:
        filename = generate_filename(a)
        write_markdown_file(
            entry=a, directory=ongoing_dir, filename=filename, entry_type="analysis"
        )
        written_analyses.add(f"{filename}.md")

    warn_about_stale_notes(published_dir, written_papers)
    warn_about_stale_notes(ongoing_dir, written_analyses)

    logger.debug("Obsidian export finished.")
    logger.debug(f"Output directory: {output_dir}")
