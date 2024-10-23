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


if __name__ == "__main__":
    # Load the papers and analyses from the CSV files. These CSV files are extracted
    # from the GLANCE database and (at the moment) need to be updated manually.
    with open("csv/papers.csv", encoding="utf8") as f:
        paper_dict = list(csv.DictReader(f))
        paper_dict = [paper.Paper.from_dict(p) for p in paper_dict]
        paper_dict.sort(key=lambda x: x.ref_code)

    with open("csv/analyses.csv", encoding="utf8") as f:
        analysis_dict = list(csv.DictReader(f))
        analysis_dict = [analysis.Analysis.from_dict(a) for a in analysis_dict]
        analysis_dict.sort(key=lambda x: x.ref_code)

    # Create a list of reference codes for unpublished papers.
    ref_codes_unpublished = [p.ref_code for p in paper_dict if p.date_submission == ""]

    # Now go through the paper dictionary and filter all that are associated to any of
    # the top WG subgroups, are submitted, and are not published since 2020.
    threshold = "2020"
    list_of_papers = []
    for p in paper_dict:
        if not any(x in p.subgroups for x in [x.id for x in subgroups.TopGroups]):
            continue

        if not p.is_submitted:
            continue

        if p.is_published and p.date_publication < threshold:
            continue

        list_of_papers.append(p)

    # Now go through the analysis dictionary and do the same: filter all that are
    # associated to any of the top WG subgroups, are not closed, and are either in
    # phase 0 or have a paper entry defined, but are not published yet.
    list_of_analyses = []
    for a in analysis_dict:
        if not any(x in p.subgroups for x in [x.id for x in subgroups.TopGroups]):
            continue

        if not (a.is_in_phase0 or a.ref_code in ref_codes_unpublished):
            continue

        if a.is_closed:
            continue

        list_of_analyses.append(a)

    # Generate the top WG overview pages in Markdown format. This creates a generic
    # overview page with links to the others, a list of all published papers, and a
    # list of all ongoing analyses.
    global_pages.overview(
        list_of_papers,
        list_of_analyses,
        output_dir="docs/analyses",
        threshold=threshold,
    )

    global_pages.published(
        list_of_papers,
        output_dir="docs/analyses",
        threshold=threshold,
    )

    global_pages.ongoing_analyses(
        list_of_analyses,
        output_dir="docs/analyses",
    )

    # Generate the subgroup overview pages in Markdown format. For each subgroup, this
    # creates an overview page with tables of all published papers and ongoing
    # analyses. Then, generate detailed pages for published papers and ongoing
    # analyses. The pages are stored in the subgroup directories.
    for g in subgroups.TopGroups:
        print(g)
        subgroup_pages.published_papers(
            list_of_papers,
            output_dir=g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
            threshold=threshold,
        )
        subgroup_pages.ongoing_analyses(
            list_of_analyses,
            output_dir=g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
        )
        subgroup_pages.overview(
            list_of_papers,
            list_of_analyses,
            output_dir=g.output_dir,
            subgroup_title=g.title,
            subgroup_id=g.id,
            threshold=threshold,
        )
