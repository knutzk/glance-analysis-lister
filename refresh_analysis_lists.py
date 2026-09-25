"""Download GLANCE tables and publish a validated registry in one refresh.

Run from the repository root. CSVs and the snapshot are left unchanged when
downloading, parsing, registry construction, or count validation fails.
"""

import argparse
import logging

import download_csv_files as downloader
from update_glance_registry import OUTPUT_DIR_JSON, build_registry

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    downloader.add_download_arguments(parser)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow an understood drop in registry counts; other checks still apply.",
    )
    args = parser.parse_args()
    tasks = downloader.download_tasks()
    snapshot_path = OUTPUT_DIR_JSON / "glance_registry.json"
    with downloader.staged_csv_files(
        tasks, **downloader.download_options(args)
    ) as staging:
        registry = build_registry(staging, snapshot_path, force=args.force)
        registry.store_json(staging / snapshot_path.name)
        downloader.publish_csv_batch(
            staging,
            downloader.CSV_DIR,
            [task["output_csv"].name for task in tasks],
            snapshot_path=snapshot_path,
        )
    logger.info(
        "Published CSV batch and registry. Render pages to preview the changes."
    )


if __name__ == "__main__":
    main()
