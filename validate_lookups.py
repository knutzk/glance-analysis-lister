"""Check maintained lookup dictionaries without GLANCE access or a snapshot."""

from analysis_lister.lookup_dicts.validation import validate_lookups

if __name__ == "__main__":
    try:
        validate_lookups()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print("All analysis lookup dictionaries are valid.")
