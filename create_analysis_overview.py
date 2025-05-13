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

from analysis_lister.glance import analysis, confnote, paper, pubnote, subgroups
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


def load_analysis_dict() -> dict[str, analysis.Analysis]:
    """Load analyses and return a lookup dictionary by ref_code."""
    analyses = load_data("analyses.csv", analysis.Analysis)
    return {a.ref_code: a for a in analyses}


def load_promoted_data(file_name, cls, base_lookup, ref_extractor):
    """Load and promote entries with analysis enrichment.

    Args:
        file_name (str): The CSV file name.
        cls (Type): Target class supporting from_analysis_and_dict().
        base_lookup (dict): Dictionary of base Analysis entries keyed by ref_code.
        ref_extractor (Callable[[dict], str]): Function to extract analysis ref_code from the row.

    Returns:
        list: List of promoted instances.
    """
    try:
        with open(CSV_DIR / file_name, encoding="utf8") as f:
            logging.info(f"Loading data from {file_name}.")
            result = []
            for row in csv.DictReader(f):
                base_ref = ref_extractor(row)
                base = base_lookup.get(base_ref)
                if not base:
                    logging.warning(
                        f"No matching analysis found for {base_ref}. Skipping."
                    )
                    continue
                result.append(cls.from_analysis_and_dict(base, row))
            logging.info(f"Loaded {len(result)} enriched entries from {file_name}.")
            return sorted(result, key=lambda x: x.ref_code)
    except FileNotFoundError:
        logging.error(f"File {file_name} not found in {CSV_DIR}.")
        raise SystemExit(f"Required CSV file '{file_name}' is missing.")


def filter_papers(papers, threshold, top_groups):
    """Prepares a filtered list of papers for overview pages."""
    filtered_papers = [
        p
        for p in papers
        if any(x in p.subgroups for x in top_groups)
        and (
            p.al_pub_state == paper.PaperPubState.SUBMITTED
            or (
                p.al_pub_state == paper.PaperPubState.PUBLISHED
                and p.date_publication >= threshold
            )
        )
    ]
    logging.info(f"Filtered {len(filtered_papers)} papers with threshold {threshold}.")
    logging.debug(
        f"Filter criteria: {top_groups} && "
        f"submitted && (not published || published after {threshold})"
    )
    return filtered_papers


def filter_analyses(analyses, top_groups):
    """Prepares a filtered list of analyses for overview pages."""
    filtered_analyses = [
        a
        for a in analyses
        if any(x in a.subgroups for x in top_groups)
        and a.al_analysis_state
        in [
            analysis.AnalysisPubState.ONGOING_WO_EB,
            analysis.AnalysisPubState.WITH_EB,
            analysis.AnalysisPubState.PRE_APPROVED,
            analysis.AnalysisPubState.PUB_PREPARATION,
        ]
    ]
    logging.info(f"Filtered {len(filtered_analyses)} active analyses.")
    logging.debug(
        f"Filter criteria: {top_groups} && "
        "(in phase 0 || unpublished publication entry) && not closed"
    )
    return filtered_analyses


def filter_confnotes(confnotes, top_groups):
    """Prepares a filtered list of confnotes for overview pages."""
    filtered_confnotes = [
        c
        for c in confnotes
        if any(x in c.subgroups for x in top_groups)
        and c.al_pub_state == confnote.ConfNotePubState.PUBLISHED
    ]
    logging.info(f"Filtered {len(filtered_confnotes)} confnotes.")
    logging.debug(f"Filter criteria: {top_groups}")
    return filtered_confnotes


def filter_pubnotes(pubnotes, top_groups):
    """Prepares a filtered list of pubnotes for overview pages."""
    filtered_pubnotes = [
        p
        for p in pubnotes
        if any(x in p.subgroups for x in top_groups)
        and p.al_pub_state == pubnote.PubNotePubState.PUBLISHED
    ]
    logging.info(f"Filtered {len(filtered_pubnotes)} pubnotes.")
    logging.debug(f"Filter criteria: {top_groups}")
    return filtered_pubnotes


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
    analyses = load_data("analyses.csv", analysis.Analysis)

    analyses_by_ref = load_analysis_dict()

    papers = load_promoted_data(
        "papers.csv",
        paper.Paper,
        analyses_by_ref,
        ref_extractor=lambda row: row["Reference Code"],
    )

    confnotes = load_promoted_data(
        "confnotes.csv",
        confnote.ConfNote,
        analyses_by_ref,
        ref_extractor=lambda row: row["Reference Code"],
    )

    pubnotes = load_promoted_data(
        "pubnotes.csv",
        pubnote.PubNote,
        analyses_by_ref,
        ref_extractor=lambda row: row["Temporary Reference Code"].removeprefix("PUB-"),
    )
    # Get modification time of the CSV files.
    mtime = determine_last_modified_time(
        [CSV_DIR / "papers.csv", CSV_DIR / "analyses.csv"]
    )

    # Go through all analyses that finished phase 0 and check if their publication
    # entries are created but not finished. If so, set the publication state to
    # "unpublished" and the publication type accordingly.
    for a in [
        x
        for x in analyses
        if x.al_analysis_state == analysis.AnalysisPubState.PAST_PHASE0
    ]:
        ref_code = a.ref_code
        if ref_code in {
            p.ref_code for p in papers if p.al_pub_state == paper.PaperPubState.ONGOING
        }:
            a.al_analysis_state = analysis.AnalysisPubState.PUB_PREPARATION
            a.glance_url_publ = (
                "https://atlas-glance.cern.ch/atlas/analysis/papers/details.php?"
                f"ref_code={a.ref_code}"
            )
            logging.debug(f"Found ongoing paper for analysis {a.ref_code}")
        elif ref_code in {
            c.tmp_ref_code.replace("CONF-", "")
            for c in confnotes
            if c.al_pub_state == confnote.ConfNotePubState.ONGOING
        }:
            a.al_analysis_state = analysis.AnalysisPubState.PUB_PREPARATION
            a.glance_url_publ = (
                "https://atlas-glance.cern.ch/atlas/analysis/confnotes/details.php?"
                f"ref_code=CONF-{a.ref_code}"
            )
            logging.debug(f"Found ongoing CONF note for analysis {a.ref_code}")
        elif ref_code in {
            p.tmp_ref_code.replace("PUB-", "")
            for p in pubnotes
            if p.al_pub_state == pubnote.PubNotePubState.ONGOING
        }:
            a.al_analysis_state = analysis.AnalysisPubState.PUB_PREPARATION
            a.glance_url_publ = (
                "https://atlas-glance.cern.ch/atlas/analysis/pubnotes/details.php?"
                f"ref_code=PUB-{a.ref_code}"
            )
            logging.debug(f"Found ongoing PUB note for analysis {a.ref_code}")

    top_groups = [x.id for x in subgroups.TopGroups]
    logging.debug(f"Top groups: {top_groups}")

    # Filter papers and analyses.
    papers = filter_papers(papers, THRESHOLD_YEAR, top_groups)
    analyses = filter_analyses(analyses, top_groups)
    confnotes = filter_confnotes(confnotes, top_groups)
    pubnotes = filter_pubnotes(pubnotes, top_groups)

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
