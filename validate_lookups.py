"""Check lookup definitions and optionally review their use in a local snapshot."""

import argparse
import logging
from pathlib import Path

from analysis_lister.lookup_dicts.validation import validate_lookups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Review factual overrides against this JSON snapshot, without editing it.",
    )
    args = parser.parse_args()
    try:
        validate_lookups()
        if args.snapshot is not None:
            # Keep source-only validation independent of registry construction.
            from analysis_lister.glance.glance_registry import GlanceRegistry
            from analysis_lister.lookup_dicts.review import lookup_review_notices

            registry = GlanceRegistry.from_json(args.snapshot)
            notices = lookup_review_notices(registry)
            for level, message in notices:
                print(f"{logging.getLevelName(level)}: {message}")
            print(f"Snapshot review: {len(notices)} notice(s); no entries changed.")
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    print("All analysis lookup dictionaries are valid.")


if __name__ == "__main__":
    main()
