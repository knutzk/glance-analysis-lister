"""Contracts shared by all model field-map parsers."""

import sys
import unittest
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.field_maps import apply_field_map


class FieldMapTests(unittest.TestCase):
    def test_preserves_raw_values_and_transforms_shared_columns_independently(self):
        row = MappingProxyType({"Status": " Phase 0 is  Active ", "Values": "a, b"})
        parsed = apply_field_map(
            row,
            {
                "status": ("Status", None),
                "values": ("Values", lambda value: value.split(", ")),
                "label": ("Values", str.upper),
            },
        )
        self.assertEqual(
            parsed,
            {
                "status": " Phase 0 is  Active ",
                "values": ["a", "b"],
                "label": "A, B",
            },
        )
        self.assertEqual(row["Values"], "a, b")

    def test_missing_and_unspecified_columns_still_reach_transforms(self):
        self.assertEqual(
            apply_field_map(
                {"": "not a source column"},
                {
                    "raw": ("Missing", None),
                    "converted": ("Missing", len),
                    "unspecified": ("", len),
                },
            ),
            {"raw": "", "converted": 0, "unspecified": 0},
        )


if __name__ == "__main__":
    unittest.main()
