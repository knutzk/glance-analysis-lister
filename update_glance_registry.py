"""Read CSV files and create a registry of glance projects.


This script reads CSV files containing information about analyses, papers, conference
notes, and publication notes, and creates a registry of these entries. The registry is
stored in a JSON file.

"""

from pathlib import Path
import logging

from analysis_lister.glance.glance_registry import GlanceRegistry


CSV_DIR = Path("csv/")
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

    logging.info("Analysis lists script finished successfully.")
