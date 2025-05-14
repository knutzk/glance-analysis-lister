import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def overview(output_dir: Path):
    """Create an analysis/paper overview page for all analyses.

    Parameters:
        output_dir: String for the output directory of the Markdown files.

    """
    logger.info("Generating overview page with tables of analyses and papers.")

    output_file = output_dir / "index.md"
    logger.info(f'Writing output file "{output_file}"')

    with open(output_file, "w", encoding="utf8") as _f:
        _f.write(
            "# Analyses and Papers\n\n\n"
            "The following pages provide an overview of all ongoing analyses and all "
            "submitted/published papers of the top group:\n\n"
            "* [Ongoing Analyses](ongoing.md)\n"
            "* [Submitted/Published Papers](published.md)\n"
            "\n\n"
            "Pages for the individual subgroups:\n\n"
            "* [Cross-section](xs/index.md)\n"
            "    * [Ongoing Analyses](xs/ongoing.md)\n"
            "    * [Submitted/Published Papers](xs/published.md)\n"
            "* [Properties & Mass](pm/index.md)\n"
            "    * [Ongoing Analyses](pm/ongoing.md)\n"
            "    * [Submitted/Published Papers](pm/published.md)\n"
            "* [Top Quarks + X](topx/index.md)\n"
            "    * [Ongoing Analyses](topx/ongoing.md)\n"
            "    * [Submitted/Published Papers](topx/published.md)\n"
            "\n"
        )

    logger.info("Finished generating overview page.")
