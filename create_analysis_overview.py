"""Module that creates analysis overview pages in Markdown format.


This script generates analysis overview pages in Markdown format for the top Working
Group (WG) and its subgroups. It uses the GlanceRegistry class to access the necessary
data and creates the pages in the specified output directory. The pages include
information about ongoing analyses, published papers, and an overview of all analyses
and papers for each subgroup.

The generated pages are saved in the specified output directory.

Optionally, the script can also generate a JSON file containing the registry data.

"""

from pathlib import Path
import logging

from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.markdown.mkdown_renderer import MarkdownPageRenderer


CSV_DIR = Path("csv/")
OUTPUT_DIR = Path("docs/analyses/")
OUTPUT_DIR_JSON = Path("json/")
THRESHOLD_YEAR = "2020"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


if __name__ == "__main__":
    logging.info("Script started.")

    registry = GlanceRegistry(
        analysis_csv="analyses.csv",
        paper_csv="papers.csv",
        confnote_csv="confnotes.csv",
        pubnote_csv="pubnotes.csv",
        csv_dir=CSV_DIR,
        threshold_year=THRESHOLD_YEAR,
    )

    registry.store_json(OUTPUT_DIR_JSON / "glance_registry.json")

    renderer = MarkdownPageRenderer(
        registry=registry,
        output_dir=OUTPUT_DIR,
        threshold_year=THRESHOLD_YEAR,
    )

    renderer.write_all()

    logging.info("Analysis lists script finished successfully.")
