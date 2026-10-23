# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Grouped citation notices remain available without the retired lookup stack."""

import logging
import unittest

from analysis_lister.diagnostics import lookup_notice, lookup_report


class CitationNoticeTests(unittest.TestCase):
    def test_nested_reports_deduplicate_and_emit_even_when_work_fails(self):
        logger = logging.getLogger("analysis_lister.synthetic")
        with (
            self.assertLogs("analysis_lister.diagnostics", level="WARNING") as logs,
            self.assertRaisesRegex(ValueError, "synthetic"),
            lookup_report(),
        ):
            lookup_notice(logger, logging.WARNING, "Invented notice %s", "one")
            with lookup_report():
                lookup_notice(logger, logging.WARNING, "Invented notice %s", "one")
            raise ValueError("synthetic")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("1 warning notice(s)", logs.output[0])
        self.assertEqual(logs.output[0].count("Invented notice"), 1)
        with self.assertLogs(logger, level="WARNING") as direct:
            lookup_notice(logger, logging.WARNING, "Direct invented notice")
        self.assertIn("Direct invented notice", direct.output[0])
