"""Module that outputs Markdown files for use in Obsidian.


"""

import logging
import re
import unicodedata
from pathlib import Path

from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.lookup_dicts.short_titles import ShortTitles
from analysis_lister.markdown.subgroup_pages.ongoing import render_analysis_block
from analysis_lister.markdown.subgroup_pages.published import render_paper_block

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


JSON_DIR = Path("json/")
OUTPUT_DIR = Path("deploy_tools/analysis_lists/obsidian_output/")
PUBLISHED_DIR = OUTPUT_DIR / "obs_published"
ONGOING_DIR = OUTPUT_DIR / "obs_ongoing"


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
    value = re.sub(r"[-\s]+", "-", value).strip("-_")
    return value


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
    if entry.ref_code in ShortTitles:
        title += f" – {ShortTitles[entry.ref_code]}"

    lines = [
        "---",
        "tags:",
        "  - TopPlusX",
        f"  - {filename}",
        f"glance-id: {entry.ref_code}",
        f"title: {title}",
        f"summary: {entry.title_short_public if entry_type == 'paper' else entry.title_short}",
    ]

    date = note_date(entry, entry_type)
    if date:
        lines.append(f"date: {date}")

    return "\n".join(lines + ["---"])


def write_markdown_file(entry, directory: Path, filename: str, entry_type: str):
    """Generalized function to write Markdown files for papers and analyses."""
    try:
        logger.info(f"Writing {entry_type} file: {filename}.md")
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
        logger.info(f"Successfully wrote {entry_type} file: {filename}.md")
    except IOError as e:
        logger.error(f"Failed to write file {filename}.md in {directory}: {e}")
        raise SystemExit(f"Failed to write file {filename}.md in {directory}: {e}")


def generate_filename(ref_code):
    """Generates a filename with the reference code and short title."""
    filename = ref_code
    if ref_code in ShortTitles:
        filename += "-" + tagify_string(ShortTitles[ref_code])
    return filename


def warn_about_stale_notes(directory: Path, written: set):
    """Report notes in an output directory that this run did not write.

    The name of a note carries its short title, so renaming one in
    `short_titles.py` leaves the note under the old name behind, and entries
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
        "%d notes in %s were not written by this run and are probably "
        "outdated: %s",
        len(stale),
        directory,
        ", ".join(stale),
    )


if __name__ == "__main__":
    # Read the same snapshot that the website is rendered from, so that the
    # notes need no CSV files and cannot drift away from the pages.
    logger.info("Loading papers and analyses data.")
    registry = GlanceRegistry.from_json(JSON_DIR / "glance_registry.json")

    # Ensure output directories exist.
    logger.info(f"Creating output directories if they do not exist: {OUTPUT_DIR}")
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    ONGOING_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Generating Markdown files for published papers.")
    written_papers = set()
    for p in registry.papers:
        filename = generate_filename(p.ref_code)
        write_markdown_file(
            entry=p, directory=PUBLISHED_DIR, filename=filename, entry_type="paper"
        )
        written_papers.add(f"{filename}.md")

    logger.info("Generating Markdown files for ongoing analyses.")
    written_analyses = set()
    for a in registry.analyses:
        filename = generate_filename(a.ref_code)
        write_markdown_file(
            entry=a, directory=ONGOING_DIR, filename=filename, entry_type="analysis"
        )
        written_analyses.add(f"{filename}.md")

    warn_about_stale_notes(PUBLISHED_DIR, written_papers)
    warn_about_stale_notes(ONGOING_DIR, written_analyses)

    logger.info("Script finished.")
    logger.info(f"Output directory: {OUTPUT_DIR}")
