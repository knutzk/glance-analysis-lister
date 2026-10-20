# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""One maintenance report per operation, with no process-wide warning cache."""

import logging
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from attrs import fields

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.lookup_dicts.reporting import lookup_notice, lookup_report
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.glance.paper import Paper
from analysis_lister.glance.subgroups import TX, XS
from analysis_lister.markdown.mkdown_renderer import MarkdownPageRenderer
from analysis_lister.refresh import compare_to_snapshot

logger = logging.getLogger(__name__)


class LookupReportingTests(unittest.TestCase):
    def test_nested_reports_deduplicate_but_keep_distinct_issues(self):
        with self.assertLogs(level="WARNING") as logs, lookup_report():
            lookup_notice(logger, logging.WARNING, "missing %s", "one")
            with lookup_report():
                lookup_notice(logger, logging.WARNING, "missing %s", "one")
                lookup_notice(logger, logging.WARNING, "missing %s", "two")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("2 lookup warning notice(s)", logs.output[0])
        self.assertEqual(logs.output[0].count("missing one"), 1)
        self.assertIn("missing two", logs.output[0])

    def test_reports_do_not_hide_warnings_in_later_runs(self):
        with self.assertLogs(level="WARNING") as logs:
            for _ in range(2):
                with lookup_report():
                    lookup_notice(logger, logging.WARNING, "missing one")
        self.assertEqual(len(logs.output), 2)

    def test_failure_flushes_report_and_restores_normal_logging(self):
        with self.assertLogs(level="WARNING") as logs:
            with self.assertRaises(ValueError), lookup_report():
                lookup_notice(logger, logging.WARNING, "before failure")
                raise ValueError("bad record")
            lookup_notice(logger, logging.WARNING, "after failure")
        self.assertEqual(len(logs.output), 2)
        self.assertIn("lookup warning notice(s)", logs.output[0])
        self.assertNotIn("lookup warning notice(s)", logs.output[1])

    def test_unrelated_warnings_are_not_collected_or_deduplicated(self):
        with self.assertLogs(level="WARNING") as logs, lookup_report():
            lookup_notice(logger, logging.WARNING, "lookup issue")
            logger.warning("unrelated issue")
            logger.warning("unrelated issue")
        self.assertEqual(len(logs.output), 3)
        self.assertIn("unrelated issue", logs.output[0])
        self.assertIn("unrelated issue", logs.output[1])
        self.assertIn("lookup issue", logs.output[2])

    def test_informational_notices_keep_their_severity(self):
        with self.assertLogs(level="INFO") as logs, lookup_report():
            lookup_notice(logger, logging.INFO, "historical override")
            lookup_notice(logger, logging.WARNING, "invalid target")
        self.assertEqual(
            [record.levelno for record in logs.records], [logging.INFO, logging.WARNING]
        )

    def test_baseline_comparison_does_not_report_old_lookup_gaps(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.touch()

            def baseline(_):
                lookup_notice(logger, logging.WARNING, "old gap")
                return GlanceRegistry()

            with (
                patch(
                    "analysis_lister.refresh.GlanceRegistry.from_json",
                    side_effect=baseline,
                ),
                patch("analysis_lister.refresh.counts", return_value={"entries": 1}),
                self.assertNoLogs(level="WARNING"),
                lookup_report(),
            ):
                self.assertEqual(compare_to_snapshot(GlanceRegistry(), path), [])
            with (
                patch(
                    "analysis_lister.refresh.GlanceRegistry.from_json",
                    side_effect=ValueError("invalid snapshot"),
                ),
                self.assertRaisesRegex(ValueError, "invalid snapshot"),
            ):
                compare_to_snapshot(object(), path)

    def test_multi_subgroup_paper_uses_glance_title_without_warnings(self):
        data = {field.name: "" for field in fields(Paper) if field.init}
        data.update(
            ref_code="TOPQ-2099-01",
            status=" Phase 0 is  Finished ",
            status_paper=" Publication Phase is  Active ",
            date_publication="2025-01-01",
            date_submission="2024-01-01",
            doi_urls=[],
            keywords=[],
            subgroups=[TX.id, XS.id],
            supporting_docs=[],
            title_short="Fallback",
        )
        paper = Paper.from_json(data)
        registry = GlanceRegistry({paper.ref_code: paper}, last_modified_time="test")
        with TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertNoLogs(level="WARNING"):
                MarkdownPageRenderer(registry, output, "2020").write_all()
            for group in (TX, XS):
                page = (output / group.output_dir / "published.md").read_text()
                self.assertIn("TOPQ-2099-01 – Fallback", page)
                self.assertIn(f"{{: #{group.code.lower()}-TOPQ-2099-01}}", page)


if __name__ == "__main__":
    unittest.main()
