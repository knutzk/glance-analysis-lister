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

import csv
from datetime import datetime
import git
import os
from pathlib import Path
from zoneinfo import ZoneInfo
import logging

from analysis_lister.glance import analysis, paper, subgroups
from analysis_lister.markdown import global_pages
from analysis_lister.markdown import subgroup_pages


CSV_DIR = Path("csv/")
OUTPUT_DIR = Path("docs/analyses/")
THRESHOLD_YEAR = "2020"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def load_data(file_name, cls):
    """Load data from a CSV file and return a sorted list of objects.

    These CSV files are extracted from the GLANCE database and (at the moment) need
    to be updated manually. The function returns a sorted list of objects instantiated
    from the CSV file data, sorted by the 'ref_code' attribute.

    Args:
        file_name (str): The name of the CSV file to load.

    Returns:
        list: Sorted list of objects instantiated from the CSV file data

    """
    try:
        with open(CSV_DIR / file_name, encoding="utf8") as f:
            logging.info(f"Loading data from {file_name}.")
            data = [cls.from_dict(item) for item in csv.DictReader(f)]
            logging.info(f"Loaded {len(data)} items from {file_name}.")
            return sorted(data, key=lambda x: x.ref_code)
    except FileNotFoundError:
        logging.error(f"File {file_name} not found in {CSV_DIR}.")
        raise SystemExit(f"Required CSV file '{file_name}' is missing.")


def filter_papers(papers, threshold, top_groups):
    """Prepares a filtered list of papers for overview pages."""
    filtered_papers = [
        p
        for p in papers
        if any(x in p.subgroups for x in top_groups)
        and p.is_submitted
        and (not p.is_published or p.date_publication >= threshold)
    ]
    logging.info(f"Filtered {len(filtered_papers)} papers with threshold {threshold}.")
    logging.debug(
        f"Filter criteria: {top_groups} && "
        f"submitted && (not published || published after {threshold})"
    )
    return filtered_papers


def filter_analyses(analyses, ref_codes_unpublished, top_groups):
    """Prepares a filtered list of analyses for overview pages."""
    filtered_analyses = [
        a
        for a in analyses
        if any(x in a.subgroups for x in top_groups)
        and (a.is_in_phase0 or a.ref_code in ref_codes_unpublished)
        and not a.is_closed
    ]
    logging.info(f"Filtered {len(filtered_analyses)} analyses.")
    logging.debug(
        f"Filter criteria: {top_groups} && "
        "(in phase 0 || unpublished paper entry) && not closed"
    )
    return filtered_analyses


def determine_last_modified_time(files):
    """Determine the last modification time of a list of files."""
    repo = git.Repo(os.getcwd())
    max_timestamp = 0

    for f in files:
        # Get the timestamp of the most recent commit affecting the file
        file_commits = list(repo.iter_commits(paths=f))
        max_timestamp = max(
            max_timestamp, file_commits[0].committed_datetime.timestamp()
        )

    last_modified_time = datetime.fromtimestamp(
        max_timestamp, tz=ZoneInfo("Europe/Zurich")
    )
    logging.info(f"Determined last modification time: {last_modified_time}")
    return last_modified_time.strftime("%b %d, %Y, %H:%M (%Z)")


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

    # Load papers and analyses data, exit if any file is missing.
    papers = load_data("papers.csv", paper.Paper)
    analyses = load_data("analyses.csv", analysis.Analysis)

    # Get modification time of the CSV files.
    mtime = determine_last_modified_time(
        [CSV_DIR / "papers.csv", CSV_DIR / "analyses.csv"]
    )

    # Create a set of analyses where a paper entry is already created, but the paper
    # is not yet submitted. In those cases, the analysis should be listed as ongoing
    # even if it is not in phase 0.
    ref_codes_unpublished = {p.ref_code for p in papers if p.date_submission == ""}
    logging.info(f"Unpublished reference codes: {ref_codes_unpublished}")
    top_groups = [x.id for x in subgroups.TopGroups]
    logging.info(f"Top groups: {top_groups}")

    # Filter papers and analyses.
    papers = filter_papers(papers, THRESHOLD_YEAR, top_groups)
    analyses = filter_analyses(analyses, ref_codes_unpublished, top_groups)

    # Generate global overview pages.
    logging.info("Generating global overview pages.")
    global_pages.overview(
        papers,
        analyses,
        output_dir=OUTPUT_DIR,
        threshold=THRESHOLD_YEAR,
    )
    global_pages.published(
        papers, output_dir=OUTPUT_DIR, last_modified=mtime, threshold=THRESHOLD_YEAR
    )
    global_pages.ongoing_analyses(analyses, last_modified=mtime, output_dir=OUTPUT_DIR)

    # Generate subgroup pages.
    generate_subgroup_pages(
        subgroups.TopGroups,
        papers,
        analyses,
        last_modified=mtime,
        threshold=THRESHOLD_YEAR,
    )

    logging.info("Script finished successfully.")
