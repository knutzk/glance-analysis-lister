"""Registry validation and transactional publication workflows.

Paths are supplied by callers. Run refreshes and registry builds sequentially.
"""

import logging
import shutil
from pathlib import Path

from analysis_lister.download import download_tasks, staged_csv_files
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.lookup_dicts.reporting import discard_lookup_notices, lookup_report
from analysis_lister.storage import CSV_REFRESH_MARKER, atomic_write_text

logger = logging.getLogger(__name__)
THRESHOLD_YEAR = "2020"
# Reject category drops greater than 20%, unless explicitly overridden.
MAX_DROP = 0.2


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
        raise ValueError(
            "Refusing to overwrite the registry, because "
            + ", and ".join(drops)
            + ". Expired cookies and renamed GLANCE columns both look like "
            "this — inspect the source data before trusting the numbers. Pass --allow-count-drop if "
            "the drop is genuine."
        )
    if drops:
        logger.warning("Writing the registry despite: %s", "; ".join(drops))

    return registry


def publish_csv_batch(
    staging: Path,
    output_dir: Path,
    filenames: list[str],
    *,
    snapshot_path: Path | None = None,
):
    """Publish a validated batch, restoring the old files on a write failure.

    The marker makes an interrupted promotion detectable by the registry loader.
    Backups remain in the staging directory if the process is killed outright.
    A fresh successful download repairs such an interrupted promotion.
    An optional staged JSON snapshot is published last using an atomic write.
    If that write fails, the CSV replacements are rolled back too.
    Run downloading and registry building sequentially.
    """
    backup = staging / "previous"
    backup.mkdir()
    for name in filenames:
        old = output_dir / name
        if old.exists():
            shutil.copy2(old, backup / name)

    marker = output_dir / CSV_REFRESH_MARKER
    was_interrupted = marker.exists()
    marker.write_text("Refresh incomplete; re-run analysis_lists.py refresh.\n")
    replaced = []
    try:
        for name in filenames:
            replaced.append(name)
            (staging / name).replace(output_dir / name)
        if snapshot_path is not None:
            atomic_write_text(
                snapshot_path, (staging / snapshot_path.name).read_text(encoding="utf8")
            )
    except BaseException:
        for name in reversed(replaced):
            previous = backup / name
            if previous.exists():
                previous.replace(output_dir / name)
            else:
                (output_dir / name).unlink(missing_ok=True)
        if not was_interrupted:
            marker.unlink()
        raise
    marker.unlink()


def refresh_csv_files(tasks, csv_dir: Path, debug_dir: Path, **options):
    """Fetch and publish CSVs only, for the standalone download command."""
    with staged_csv_files(tasks, csv_dir, debug_dir, **options) as staging:
        publish_csv_batch(staging, csv_dir, [t["output_csv"].name for t in tasks])
    logger.info("Published complete CSV batch.")


def update_registry(csv_dir: Path, snapshot_path: Path, *, force=False):
    """Validate existing CSVs and atomically publish their registry."""
    registry = build_registry(csv_dir, snapshot_path, force=force)
    registry.store_json(snapshot_path)


def refresh_analysis_lists(
    csv_dir: Path, debug_dir: Path, snapshot_path: Path, *, force=False, **options
):
    """Stage and validate all inputs before publishing CSVs and JSON together."""
    tasks = download_tasks(csv_dir)
    with staged_csv_files(tasks, csv_dir, debug_dir, **options) as staging:
        registry = build_registry(staging, snapshot_path, force=force)
        registry.store_json(staging / snapshot_path.name)
        publish_csv_batch(
            staging,
            csv_dir,
            [t["output_csv"].name for t in tasks],
            snapshot_path=snapshot_path,
        )
    logger.info(
        "Published CSV batch and registry. Render pages to preview the changes."
    )
