"""Validate CSV files and publish the GLANCE registry."""

import argparse

from analysis_lister.cli import (
    CSV_DIR,
    SNAPSHOT_PATH,
    command_errors,
    configure_logging,
)
from analysis_lister.refresh import update_registry


def main(argv=None):
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow an understood drop in registry counts; other checks still apply.",
    )
    args = parser.parse_args(argv)
    with command_errors():
        update_registry(CSV_DIR, SNAPSHOT_PATH, force=args.force)


if __name__ == "__main__":
    main()
