"""Download GLANCE tables and publish a validated registry in one refresh."""

import argparse

from analysis_lister.cli import (
    COOKIE_FILE,
    CSV_DIR,
    DEBUG_DIR,
    SNAPSHOT_PATH,
    add_download_arguments,
    command_errors,
    configure_logging,
)
from analysis_lister.download import download_options
from analysis_lister.refresh import refresh_analysis_lists


def main(argv=None):
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    add_download_arguments(parser)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow an understood drop in registry counts; other checks still apply.",
    )
    args = parser.parse_args(argv)
    with command_errors():
        options = download_options(
            COOKIE_FILE,
            use_local_html=args.use_local_html,
            generate_new_cookies=args.generate_new_cookies,
            debug=args.debug,
        )
        refresh_analysis_lists(
            CSV_DIR, DEBUG_DIR, SNAPSHOT_PATH, force=args.force, **options
        )


if __name__ == "__main__":
    main()
