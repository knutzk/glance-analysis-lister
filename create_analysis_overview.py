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

from analysis_lister.glance import analysis, paper, subgroups
from analysis_lister.markdown import global_pages
from analysis_lister.markdown import subgroup_pages


CSV_PATH = "csv/"
OUTPUT_DIR = "docs/analyses/"
THRESHOLD_YEAR = "2020"


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
    with open(f"{CSV_PATH}{file_name}", encoding="utf8") as f:
        return sorted(
            [cls.from_dict(item) for item in csv.DictReader(f)],
            key=lambda x: x.ref_code,
        )


def filter_papers(papers, threshold, top_groups):
    """Prepares a filtered list of papers that should go onto the pages.

    The following filters are applied:
    - The paper must belong to one of the top groups.
    - The paper must be submitted.
    - The paper must either not be published or have a publication date on or after
      the threshold (to cut off very lengthy publication lists).

    Args:
        papers (list): A list of paper objects to be filtered.
        threshold (datetime): The date threshold for publication.
        top_groups (list): A list of top group names to filter by.

    Returns:
        list: Filtered list of papers.

    """
    return [
        p
        for p in papers
        if any(x in p.subgroups for x in top_groups)
        and p.is_submitted
        and (not p.is_published or p.date_publication >= threshold)
    ]


def filter_analyses(analyses, ref_codes_unpublished, top_groups):
    """Prepares a filtered list of analyses that should go onto the pages.

    The following filters are applied:
    - The analysis belongs to any of the top groups.
    - The analysis is either in phase 0 or its reference code is in the set of
      unpublished reference codes (those should be listed as ongoing).
    - The analysis is not closed.

    Args:
        analyses (list): A list of analysis objects to be filtered.
        ref_codes_unpublished (set): A set of reference codes for unpublished analyses.
        top_groups (set): A set of top subgroups.

    Returns:
        list: Filtered list of analyses.

    """
    return [
        a
        for a in analyses
        if any(x in a.subgroups for x in top_groups)
        and (a.is_in_phase0 or a.ref_code in ref_codes_unpublished)
        and not a.is_closed
    ]


def generate_subgroup_pages(subgroups, papers, analyses, threshold):
    """Generate the subgroup overview pages in Markdown format.

    For each subgroup, this function creates an overview page with tables of all
    published papers and ongoing analyses. Then, it generates detailed pages for
    published papers and ongoing analyses. The pages are stored in the subgroup
    directories.

    Args:
        subgroups (list): A list of subgroups to be considered for the pages.
        papers (list): A list of paper objects to be included in the pages.
        analyses (list): A list of analysis objects to be included in the pages.
        threshold (int): A threshold value used for filtering the papers.

    """
    for g in subgroups:
        subgroup_pages.published_papers(
            papers,
            output_dir=g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
            threshold=threshold,
        )
        subgroup_pages.ongoing_analyses(
            analyses,
            output_dir=g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
        )
        subgroup_pages.overview(
            papers,
            analyses,
            output_dir=g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
            threshold=threshold,
        )


if __name__ == "__main__":
    papers = load_data("papers.csv", paper.Paper)
    analyses = load_data("analyses.csv", analysis.Analysis)

    # Create a list of analyses where a paper entry is already created, but the paper
    # is not yet submitted. In those cases, the analysis should be listed as ongoing
    # even if it is not in phase 0.
    ref_codes_unpublished = [p.ref_code for p in papers if p.date_submission == ""]

    top_groups = [x.id for x in subgroups.TopGroups]
    papers = filter_papers(papers, THRESHOLD_YEAR, top_groups)
    analyses = filter_analyses(analyses, ref_codes_unpublished, top_groups)

    global_pages.overview(
        papers,
        analyses,
        output_dir=OUTPUT_DIR,
        threshold=THRESHOLD_YEAR,
    )
    global_pages.published(papers, output_dir=OUTPUT_DIR, threshold=THRESHOLD_YEAR)
    global_pages.ongoing_analyses(analyses, output_dir=OUTPUT_DIR)

    generate_subgroup_pages(subgroups.TopGroups, papers, analyses, THRESHOLD_YEAR)
