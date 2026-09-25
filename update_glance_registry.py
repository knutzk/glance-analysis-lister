"""Read CSV files and create a registry of glance projects.


This script reads CSV files containing information about analyses, papers, conference
notes, and publication notes, and creates a registry of these entries. The registry is
stored in a JSON file.

Before overwriting that file, the counts of the new registry are compared against
the ones of the committed snapshot. A download that returned a login page, or a
GLANCE table whose columns were renamed, shows up as a sharp drop rather than as
an error, and the JSON file is the only input the website is built from — so a
drop stops the script instead of being written out.

"""

import argparse
import logging
from pathlib import Path

from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.lookup_dicts.reporting import discard_lookup_notices, lookup_report

CSV_DIR = Path("deploy_tools/analysis_lists/csv/")
OUTPUT_DIR_JSON = Path("json/")
THRESHOLD_YEAR = "2020"

# Fraction of its entries a category may lose before the run is stopped. Single
# entries do drop out legitimately — an analysis is closed, a note superseded —
# so the check is meant to catch a category collapsing, not to be exact.
MAX_DROP = 0.2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def counts(registry: GlanceRegistry) -> dict[str, int]:
    """Return the number of entries a registry lists, per category."""
    return {
        "entries": len(registry.entries),
        "ongoing analyses": len(registry.analyses),
        "papers": len(registry.papers),
        "CONF notes": len(registry.confnotes),
        "PUB notes": len(registry.pubnotes),
    }


def compare_to_snapshot(registry: GlanceRegistry, path: Path) -> list[str]:
    """Compare the counts of a new registry against the committed snapshot.

    Args:
        registry: The newly built registry.
        path: Path of the snapshot to compare against.

    Returns:
        One message per category that lost more than MAX_DROP of its entries,
        empty if the new registry is plausible or there is nothing to compare
        it against.

    """
    if not path.exists():
        logger.info("No snapshot at %s yet, nothing to compare against.", path)
        return []

    with discard_lookup_notices():
        old = counts(GlanceRegistry.from_json(path))
    new = counts(registry)

    drops = []
    for label, old_count in old.items():
        new_count = new[label]
        logger.info("%s: %d -> %d", label, old_count, new_count)
        if new_count < old_count * (1 - MAX_DROP):
            drops.append(f"{label} dropped from {old_count} to {new_count}")

    return drops


@lookup_report()
def build_registry(csv_dir: Path, output_path: Path, *, force: bool = False):
    """Build and validate a candidate registry without publishing it."""
    registry = GlanceRegistry(
        analysis_csv="analyses.csv",
        paper_csv="papers.csv",
        confnote_csv="confnotes.csv",
        pubnote_csv="pubnotes.csv",
        csv_dir=csv_dir,
        threshold_year=THRESHOLD_YEAR,
    )

    drops = compare_to_snapshot(registry, output_path)
    if drops and not force:
        raise SystemExit(
            "Refusing to overwrite the registry, because "
            + ", and ".join(drops)
            + ". Expired cookies and renamed GLANCE columns both look like "
            "this — inspect the source data before trusting the numbers. Pass --force if "
            "the drop is genuine."
        )
    if drops:
        logger.warning("Writing the registry despite: %s", "; ".join(drops))

    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write the registry even if its counts dropped sharply.",
    )
    args = parser.parse_args()

    logger.info("Script started.")

    output_path = OUTPUT_DIR_JSON / "glance_registry.json"
    registry = build_registry(CSV_DIR, output_path, force=args.force)
    registry.store_json(output_path)

    logger.info("Analysis lists script finished successfully.")


if __name__ == "__main__":
    main()
