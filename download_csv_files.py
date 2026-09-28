"""Fetch data and generate CSV files."""

import argparse

from analysis_lister.cli import (
    COOKIE_FILE,
    CSV_DIR,
    DEBUG_DIR,
    add_download_arguments,
    command_errors,
    configure_logging,
)
from analysis_lister.download import download_options, download_tasks
from analysis_lister.refresh import refresh_csv_files


def main(argv=None):
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    add_download_arguments(parser)
    args = parser.parse_args(argv)
    with command_errors():
        options = download_options(
            COOKIE_FILE,
            use_local_html=args.use_local_html,
            generate_new_cookies=args.generate_new_cookies,
            debug=args.debug,
        )
        refresh_csv_files(download_tasks(CSV_DIR), CSV_DIR, DEBUG_DIR, **options)


if __name__ == "__main__":
    main()
