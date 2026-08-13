"""Module that creates analysis overview pages in Markdown format.


This script generates analysis overview pages in Markdown format for the top Working
Group (WG) and its subgroups. It uses the GlanceRegistry class to access the necessary
data and creates the pages in the specified output directory. The pages include
information about ongoing analyses, published papers, and an overview of all analyses
and papers for each subgroup.

The generated pages are saved in the specified output directory.

"""

import logging
from pathlib import Path

from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.markdown.mkdown_renderer import MarkdownPageRenderer

OUTPUT_DIR = Path("docs/analyses/")
JSON_DIR = Path("json/")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Script started.")

    registry = GlanceRegistry.from_json(JSON_DIR / "glance_registry.json")
    registry.log_unaccounted()

    renderer = MarkdownPageRenderer(
        registry=registry,
        output_dir=OUTPUT_DIR,
        threshold_year=registry.threshold_year,
    )

    renderer.write_all()

    logger.info("All Markdown pages created. Finished successfully.")
