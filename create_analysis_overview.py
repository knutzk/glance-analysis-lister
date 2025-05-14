"""Module that creates analysis overview pages in Markdown format.


This script generates analysis overview pages in Markdown format for the top Working Group (WG) subgroups.

The script performs the following tasks:
1. Loads papers and analyses from CSV files.
2. Filters papers associated with top WG subgroups that are submitted and not published since 2020.
3. Filters analyses associated with top WG subgroups that are not closed and either in phase 0 or have an unpublished paper entry.
4. Generates global overview pages in Markdown format, including:
    - A generic overview page with links to other pages.
    - A list of all published papers.
    - A list of all ongoing analyses.
5. Generates subgroup overview pages in Markdown format, including:
    - Tables of all published papers and ongoing analyses for each subgroup.
    - Detailed pages for published papers and ongoing analyses, stored in subgroup directories.

"""

from pathlib import Path
import logging

from analysis_lister.glance import subgroups
from analysis_lister.markdown import global_pages
from analysis_lister.markdown import subgroup_pages


CSV_DIR = Path("csv/")
OUTPUT_DIR = Path("docs/analyses/")
THRESHOLD_YEAR = "2020"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def generate_subgroup_pages(subgroups, papers, analyses, last_modified, threshold):
    """Generate the subgroup overview pages in Markdown format."""
    for g in subgroups:
        logging.info(f"Generating pages for subgroup: {g.title}")
        subgroup_pages.published_papers(
            papers,
            output_dir=OUTPUT_DIR / g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
            last_modified=last_modified,
            threshold=threshold,
        )
        subgroup_pages.ongoing_analyses(
            analyses,
            output_dir=OUTPUT_DIR / g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
            last_modified=last_modified,
        )
        subgroup_pages.overview(
            papers,
            analyses,
            output_dir=OUTPUT_DIR / g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
            last_modified=last_modified,
            threshold=threshold,
        )


if __name__ == "__main__":
    logging.info("Script started.")

    from analysis_lister.glance import glance_registry

    registry = glance_registry.GlanceRegistry(
        analysis_csv="analyses.csv",
        paper_csv="papers.csv",
        confnote_csv="confnotes.csv",
        pubnote_csv="pubnotes.csv",
        csv_dir=CSV_DIR,
        threshold_year=THRESHOLD_YEAR,
    )

    analyses, papers, confnotes, pubnotes = (
        registry.analyses_filtered,
        registry.papers_filtered,
        registry.confnotes_filtered,
        registry.pubnotes_filtered,
    )

    mtime = registry.determine_last_modified_time()

    # Generate global overview pages.
    logging.info("=" * 80)
    logging.info("Generating global pages for the top group.")
    logging.info("=" * 80)
    global_pages.overview(output_dir=OUTPUT_DIR)
    global_pages.published(
        papers, output_dir=OUTPUT_DIR, last_modified=mtime, threshold=THRESHOLD_YEAR
    )
    global_pages.ongoing_analyses(analyses, last_modified=mtime, output_dir=OUTPUT_DIR)

    # Generate subgroup pages.
    logging.info("=" * 80)
    logging.info(f"Generating subgroup pages for {len(subgroups.TopGroups)} subgroups.")
    logging.info("=" * 80)
    generate_subgroup_pages(
        subgroups.TopGroups,
        papers,
        analyses,
        last_modified=mtime,
        threshold=THRESHOLD_YEAR,
    )

    logging.info("Analysis lists script finished successfully.")
