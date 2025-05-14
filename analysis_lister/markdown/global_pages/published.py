import logging
from pathlib import Path
from typing import List

from analysis_lister.glance import subgroups
from analysis_lister.glance.enums import PublicationState
from analysis_lister.glance.paper import Paper
from ..render import utils

logger = logging.getLogger(__name__)


def published(
    list_of_papers: list[Paper],
    output_dir: Path,
    last_modified: str,
    threshold: str = "2020",
):
    """Create a list of submitted and published papers.

    Parameters:
        list_of_papers: A list of paper objects considered for the tables.
        output_dir: String for the output directory of the Markdown file.
        threshold: Threshold in the form of a date that is used to set a limit
            on the number of listed publications (only newer than 'threshold').

    """
    logger.info("Generating published papers overview.")

    n_published = sum(x.pub_state == PublicationState.PUBLISHED for x in list_of_papers)
    n_submitted = sum(
        x.pub_state == PublicationState.SUBMITTED_TO_JOURNAL for x in list_of_papers
    )

    logger.debug(f"Found {n_published} published and {n_submitted} submitted papers.")

    output_file = output_dir / "published.md"
    logger.info(f'Writing output file "{output_file}"')

    with open(output_file, "w", encoding="utf8") as _f:
        _f.write("---\nhide:\n -toc\n---\n\n\n")
        _f.write("# Submitted/published papers\n\n")

        _f.write(utils.print_header_timestamp(last_modified))

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

        logger.info("Writing detailed paper counts for published papers.")
        _f.write(f'!!! info "Counts per subgroup (since {threshold})"\n\n')
        for g in subgroups.TopGroups:
            count = sum(g.id in x.subgroups for x in list_of_papers)
            _f.write(f"    * {g.title}: {count} (")
            count = sum(
                1
                for x in list_of_papers
                if g.id in x.subgroups and x.pub_state == PublicationState.PUBLISHED
            )
            _f.write(f"published: {count}, ")
            count = sum(
                1
                for x in list_of_papers
                if g.id in x.subgroups
                and x.pub_state == PublicationState.SUBMITTED_TO_JOURNAL
            )
            _f.write(f"submitted: {count})\n")

        _f.write("\n\n")

        _f.write("| Identifier | Title | Subgroup | Submission | Publication |\n")
        _f.write("| --- | --- | --- | --- | --- |\n")

        def _get_top_subgroup_codes(grps: List[str]) -> str:
            """Get the top subgroup codes from a list of subgroup codes."""
            top_subgroups = [g.code for g in subgroups.TopGroups if g.id in grps]
            return ", ".join(top_subgroups) if top_subgroups else "None"

        for p in list_of_papers:
            logger.debug(f"Writing table row for paper {p.ref_code}.")
            _f.write(
                f'| [{p.ref_code.replace("-", "&#8209;")}][{p.ref_code}] '
                f"| {p.title_short} "
                f"| {_get_top_subgroup_codes(p.subgroups)} "
                f'| {p.date_submission.replace("-", "&#8209;")} '
                f'| {p.date_publication.replace("-", "&#8209;")} '
                f"|\n",
            )
