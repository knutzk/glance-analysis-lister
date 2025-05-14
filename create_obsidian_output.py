"""Module that outputs Markdown files for use in Obsidian.


"""

import logging
from pathlib import Path
import re
import unicodedata

from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.markdown.render.analysis import render_analysis_block
from analysis_lister.markdown.render.paper import render_paper_block
from analysis_lister.lookup_dicts.short_titles import ShortTitles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


CSV_DIR = Path("csv/")
OUTPUT_DIR = Path("deploy_tools/analysis_lists/obsidian_output/")
PUBLISHED_DIR = OUTPUT_DIR / "obs_published"
ONGOING_DIR = OUTPUT_DIR / "obs_ongoing"
THRESHOLD_YEAR = "2020"


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


def write_markdown_file(entry, directory: Path, filename: str, entry_type: str):
    """Generalized function to write Markdown files for papers and analyses."""
    try:
        logger.info(f"Writing {entry_type} file: {filename}.md")
        with open(directory / f"{filename}.md", "w") as f:
            f.write(
                f"""---
tags:
  - TopPlusX
  - {filename}
glance-id: {entry.ref_code}
title: {entry.ref_code}{f" – {ShortTitles[entry.ref_code]}" if entry.ref_code in ShortTitles else ""}
summary: {entry.title_short_public if entry_type == "paper" else entry.title_short}
{"date: " + entry.date_start if entry_type == "analysis" else ""}
---

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


if __name__ == "__main__":
    # Load papers and analyses data, exit if any file is missing.
    logger.info("Loading papers and analyses data.")
    registry = GlanceRegistry(
        analysis_csv="analyses.csv",
        paper_csv="papers.csv",
        confnote_csv="confnotes.csv",
        pubnote_csv="pubnotes.csv",
        csv_dir=CSV_DIR,
        threshold_year=THRESHOLD_YEAR,
    )

    # Ensure output directories exist.
    logger.info(f"Creating output directories if they do not exist: {OUTPUT_DIR}")
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    ONGOING_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Generating Markdown files for published papers.")
    for p in registry.papers_filtered:
        filename = generate_filename(p.ref_code)
        write_markdown_file(
            entry=p, directory=PUBLISHED_DIR, filename=filename, entry_type="paper"
        )

    logger.info("Generating Markdown files for ongoing analyses.")
    for a in registry.analyses_filtered:
        filename = generate_filename(a.ref_code)
        write_markdown_file(
            entry=a, directory=ONGOING_DIR, filename=filename, entry_type="analysis"
        )

    logger.info("Script finished.")
    logger.info(f"Output directory: {OUTPUT_DIR}")
