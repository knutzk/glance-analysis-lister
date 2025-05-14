"""Module that creates analysis overview pages in Markdown format.


This script generates analysis overview pages in Markdown format for the top Working Group (WG) subgroups.

"""

from pathlib import Path
import logging

from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.markdown.mkdown_renderer import MarkdownPageRenderer


CSV_DIR = Path("csv/")
OUTPUT_DIR = Path("docs/analyses/")
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

    renderer = MarkdownPageRenderer(
        registry=registry,
        output_dir=OUTPUT_DIR,
        threshold_year=THRESHOLD_YEAR,
    )

    renderer.write_all()

    logging.info("Analysis lists script finished successfully.")
