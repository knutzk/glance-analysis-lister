import logging
from pathlib import Path
from analysis_lister.glance.analysis import Analysis as GlanceAnalysis
from analysis_lister.glance.paper import Paper as GlancePaper
from ..render.tables import render_analysis_table, render_paper_table
from ..render import utils

logger = logging.getLogger(__name__)

def overview(
    list_of_papers: list[GlancePaper],
    list_of_analyses: list[GlanceAnalysis],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
    threshold: str = "2020",
):
    """Create an analysis/paper overview page for one subgroup."""
    subgroup_papers = [p for p in list_of_papers if subgroup_id in p.subgroups]
    subgroup_analyses = [a for a in list_of_analyses if subgroup_id in a.subgroups]

    logger.info(f'Writing output file "{output_dir}/index.md"')
    with open(output_dir / "index.md", "w", encoding="utf8") as _f:
        _f.write("---\nhide:\n -toc\n---\n\n\n")
        _f.write(f"# {subgroup_title} – Analyses and Papers\n\n\n")
        _f.write(utils.print_header_timestamp(last_modified))

        logger.info(
            f'Found {len(subgroup_analyses)} ongoing analyses for subgroup "{subgroup_id}".'
        )
        _f.write("## Ongoing Analyses\n\n")
        _f.write(
            f"There are currently {len(subgroup_analyses)} ongoing analyses "
            f'for which "{subgroup_id}" is listed as the leading or an '
            "additional subgroup.\n\n"
            '- The "**EB PA A**" column indicates the review status of the analyses:\n'
            "    - One tick mark = EdBoard is assigned (EB),\n"
            "    - two tick marks = analysis is pre-approved (PA),\n"
            "    - three tick marks = analysis is group-approved (A).\n"
            '- "**Rel.**" shows the software release the analysis uses – it is based '
            "on the keywords assigned to the analysis on GLANCE.\n"
            '- "**Start**" is the date the analysis started.\n\n'
        )
        _f.write(render_analysis_table(subgroup_analyses))
        _f.write("\n\n\n")

        logger.info(
            f"Found {len(subgroup_papers)} submitted and published papers for "
            f'subgroup "{subgroup_id}".'
        )
        _f.write("## Submitted/Published Papers\n\n")
        _f.write(
            f"There are {len(subgroup_papers)} submitted and published papers "
            f'for which "{subgroup_id}" is listed as the leading or an '
            "additional subgroup (only considering papers published in "
            f"{threshold} or after).\n\n"
        )
        _f.write(render_paper_table(subgroup_papers))

    logger.info(f"Finished writing overview page for subgroup '{subgroup_id}'.")
