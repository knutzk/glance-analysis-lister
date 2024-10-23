"""Create global overview pages in Markdown for the entire top WG.


"""

from typing import List

from analysis_lister.glance import analysis, paper, subgroups
from . import utils


def published(
    list_of_papers: list[paper.Paper],
    output_dir: str,
    threshold: str = "2020",
):
    """Create a list of submitted and published papers.

    Parameters:
        list_of_papers: A list of paper objects considered for the tables.
        output_dir: String for the output directory of the Markdown file.
        threshold: Threshold in the form of a date that is used to set a limit
            on the number of listed publications (only newer than 'threshold').

    """
    n_published = sum(1 for x in list_of_papers if x.is_published)
    n_submitted = sum(
        1 for x in list_of_papers if x.is_submitted and not x.is_published
    )
    print(f'Writing output file "{output_dir}/published.md"')
    with open(f"{output_dir}/published.md", "w", encoding="utf8") as _f:
        _f.write("---\nhide:\n -toc\n---\n\n\n")
        _f.write("# Submitted/published papers\n\n")
        link = "https://twiki.cern.ch/twiki/bin/view/AtlasPublic/TopPublicResults"
        _f.write(
            f"There are currently {n_submitted} submitted papers for which "
            "one or more of the ATLAS top WG subgroups is listed as the "
            "leading or an additional subgroup.\n"
            f"In addition, {n_published} papers have been published since "
            f"{threshold}.\n\n"
            "These and older publications are also listed on the "
            f"[TopPublicResults twiki page]({link}).\n\n"
        )

        _f.write(f'!!! info "Counts per subgroup (since {threshold})"\n\n')
        for g in subgroups.TopGroups:
            count = sum(1 for x in list_of_papers if g in x.top_subgroups)
            _f.write(f"    * {g.title}: {count} (")
            count = sum(
                1 for x in list_of_papers if g in x.top_subgroups and x.is_published
            )
            _f.write(f"published: {count}, ")
            count = sum(
                1
                for x in list_of_papers
                if g in x.top_subgroups and not x.is_published and x.is_submitted
            )
            _f.write(f"submitted: {count})\n")

        _f.write("\n\n")

        _f.write("| Identifier | Title | Subgroup | Submission | Publication |\n")
        _f.write("| --- | --- | --- | --- | --- |\n")
        for p in list_of_papers:
            _f.write(
                f'| [{p.ref_code.replace("-", "&#8209;")}][{p.ref_code}] '
                f"| {p.title_short} "
                f'| {", ".join([g.code for g in p.top_subgroups])} '
                f'| {p.date_submission.replace("-", "&#8209;")} '
                f'| {p.date_publication.replace("-", "&#8209;")} '
                f"|\n",
            )

        _f.write("\n\n\n")
        # _f.write(utils.print_footer_timestamps("csv/analyses.csv", "csv/papers.csv"))


def ongoing_analyses(
    list_of_analyses: list[analysis.Analysis],
    output_dir: str,
):
    """Create a page with ongoing analyses for one subgroup.

    Takes a list of analyses and produces a Markdown page with subsections for
    each analysis. The analyses are filtered based on the 'subgroup_id' string
    being part of the 'Subgroups' field in GLANCE. The analyses are listed
    in separate subsectinos depending on their stage in the approval process.

    Parameters:
        list_of_analyses: A list of analysis objects considered for the table.
        output_dir: String for the output directory of the Markdown file.

    """
    print(f'Writing output file "{output_dir}/ongoing.md"')
    with open(f"{output_dir}/ongoing.md", "w", encoding="utf8") as _f:
        _f.write("---\nhide:\n -toc\n---\n\n\n")
        _f.write("# Ongoing analyses\n\n\n")

        _f.write(
            "The following table lists all ongoing analyses in the ATLAS top WG.\n"
            'The "**EB PA A**" column indicates the review status of the analyses:\n'
            "One tick mark = EdBoard is assigned (EB),\n"
            "two tick marks = analysis is pre-approved (PA),\n"
            "three tick marks = analysis is group-approved (A).\n"
            'The "**Subgroups**" column lists all top WG subgroups involved in the '
            "analysis.\n"
            '"**Rel.**" shows the software release the analysis uses – it is based '
            "on the keywords assigned to the analysis on GLANCE.\n\n"
        )

        def provide_counts(alist: List[analysis.Analysis], criteria: bool):
            """Provide total count and count per release.

            Parameters:
                alist: The list of analyses to consider.
                criteria: The criteria to apply for filtering.

            Returns: String with analysis counts fulfilling these criteria
                (total count, count in R21, count in R25, unknown).

            """
            filtered = [x for x in alist if criteria(x)]
            f_R21 = sum(1 for x in filtered if "R21" in x.keywords)
            f_R25 = sum(1 for x in filtered if "R22" in x.keywords)
            return (
                f"{len(filtered)} ({f_R21} analyses in R21, {f_R25} analyses "
                f"in R25, {len(filtered) - f_R21 - f_R25} unknown)"
            )

        _f.write('!!! info "Detailed analysis counts"\n\n')
        _f.write("    * **All ongoing analyses**: ")
        _f.write(provide_counts(list_of_analyses, lambda _: True))
        _f.write("\n")

        # =====================================================================
        # Split by subgroup
        # =====================================================================
        _f.write("    * **Split by subgroup** (double-counts possible):\n")
        for g in subgroups.TopGroups:
            count = sum(1 for x in list_of_analyses if g in x.top_subgroups)
            _f.write(f"        * {g.title}: {count} (")
            count = sum(
                1 for x in list_of_analyses if g in x.top_subgroups and x.is_preapproved
            )
            _f.write(f"pre-approved: {count}, ")
            count = sum(
                1
                for x in list_of_analyses
                if g in x.top_subgroups and not x.is_preapproved and x.is_with_edboard
            )
            _f.write(f"with EdBoard: {count}, ")
            count = sum(
                1
                for x in list_of_analyses
                if g in x.top_subgroups and not x.is_with_edboard
            )
            _f.write(f"no EdBoard: {count})\n")

        # =====================================================================
        # Split by status
        # =====================================================================
        _f.write("    * **Split by status**:")
        _f.write("\n        * Approved: ")
        _f.write(provide_counts(list_of_analyses, lambda x: x.is_approved))
        _f.write("\n        * Pre-approved: ")
        _f.write(
            provide_counts(
                list_of_analyses, lambda x: x.is_preapproved and not x.is_approved
            )
        )
        _f.write("\n        * With EdBoard: ")
        _f.write(
            provide_counts(
                list_of_analyses, lambda x: not x.is_preapproved and x.is_with_edboard
            )
        )
        _f.write("\n        * No EdBoard: ")
        _f.write(provide_counts(list_of_analyses, lambda x: not x.is_with_edboard))
        _f.write("\n\n\n")

        _f.write("| Identifier | Title | EB PA A | Subgroups | Rel. | Start |\n")
        _f.write("| --- | --- | --- | --- | --- | --- |\n")
        for a in list_of_analyses:
            release_str = ""
            if "R22" in a.keywords:
                release_str = "R25"
            elif "R21" in a.keywords:
                release_str = "R21"

            _f.write(
                f'| [{a.ref_code.replace("-", "&#8209;")}][{a.ref_code}] '
                f"| {a.title_short} "
                f'| {"&#10003;&nbsp;" if a.is_with_edboard else ""}'
                f'{"&#10003;&nbsp;" if a.is_preapproved else ""}'
                f'{"&#10003;&nbsp;" if a.is_approved else ""}'
                f'| {", ".join([g.code for g in a.top_subgroups])} '
                f"| {release_str} "
                f'| {a.date_start.replace("-", "&#8209;")} '
                f"|\n",
            )

        _f.write("\n\n\n")

        # _f.write(utils.print_footer_timestamps("csv/analyses.csv"))


def overview(
    list_of_papers: list[paper.Paper],
    list_of_analyses: list[analysis.Analysis],
    output_dir: str,
    threshold: str = "2020",
):
    """Create an analysis/paper overview page for all analyses.

    Takes a list of papers and a list of analyses, and produces a Markdown
    page with overview tables of both. Only papers published in 'threshold'
    or later will be listed.

    Parameters:
        list_of_papers: list of papers considered for the overview tables.
        list_of_analyses: list of analyses considered for the overview tables.
        output_dir: String for the output directory of the Markdown files.
        threshold: Threshold in the form of a date that is used to set a limit
            on the number of listed publications (only newer than 'threshold').

    """
    print(f'Writing output file "{output_dir}/index.md"')
    with open(f"{output_dir}/index.md", "w", encoding="utf8") as _f:
        _f.write(
            "# ATLAS top WG analyses\n\n\n"
            "Jump to the overall analysis/paper lists:\n\n"
            "* [Submitted/published papers](published.md)\n"
            "* [Ongoing analyses](ongoing.md)\n\n\n"
            "Pages for the individual subgroups:\n\n"
            "* [Top Quarks + X](topx/index.md)\n"
            "    * [Submitted/published papers](topx/published.md)\n"
            "    * [Ongoing analyses](topx/ongoing.md)\n"
            "* [Top Cross Section](xsec/index.md)\n"
            "    * [Submitted/published papers](xsec/published.md)\n"
            "    * [Ongoing analyses](xsec/ongoing.md)\n"
            "* [Top Properties & Mass](pnm/index.md)\n"
            "    * [Submitted/published papers](pnm/published.md)\n"
            "    * [Ongoing analyses](pnm/ongoing.md)\n"
            "\n\n\n",
        )
