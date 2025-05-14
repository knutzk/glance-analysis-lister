import logging
from pathlib import Path
from analysis_lister.glance.analysis import Analysis as GlanceAnalysis
from analysis_lister.glance.enums import PublicationState
from ..render.analysis import render_analysis_block
from ..render import utils

logger = logging.getLogger(__name__)

def ongoing_analyses(
    list_of_analyses: list[GlanceAnalysis],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
):
    """Create a page with ongoing analyses for one subgroup."""
    subgroup_analyses = [a for a in list_of_analyses if subgroup_id in a.subgroups]

    logger.info(f'Writing output file "{output_dir}/ongoing.md"')
    with open(output_dir / "ongoing.md", "w", encoding="utf8") as _f:
        _f.write(f"# {subgroup_title} – Ongoing Analyses\n\n\n")
        _f.write(utils.print_header_timestamp(last_modified))

        logger.info(
            f'Found {len(subgroup_analyses)} ongoing analyses for subgroup "{subgroup_id}".'
        )
        _f.write(
            f"There are currently {len(subgroup_analyses)} ongoing analyses "
            f'for which "{subgroup_id}" is listed as the leading or an '
            "additional subgroup.\n"
            "The following lists separate those analyses beyond the subgroup "
            "pre-approval, those with an Editorial Board assigned, and those "
            "without an Editorial Board.\n\n\n"
        )

        _f.write("## Analyses beyond pre-approval\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state in [
                PublicationState.PREAPPROVED,
                PublicationState.PHASE1_OR_2,
            ]:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(render_analysis_block(a))

        _f.write("## Analyses with EdBoard\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state == PublicationState.ONGOING_WITH_EB:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(render_analysis_block(a))

        _f.write("## Analyses w/o EdBoard\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state == PublicationState.ONGOING_WO_EB:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(render_analysis_block(a))

    logger.info(f"Finished writing ongoing analyses page for subgroup '{subgroup_id}'.")
