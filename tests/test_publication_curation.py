# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publication policies, configuration and explicit affiliation inheritance."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from view_fixtures import analysis, publication, snapshot

from analysis_lister import cli
from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.build import render_group
from analysis_lister.views.markdown.pages import (
    confnotes_page,
    ongoing_page,
    papers_page,
    pubnotes_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

ROOT = Path(__file__).resolve().parents[1]


class ArchiveCurationPolicyTests(unittest.TestCase):
    def test_all_resources_use_identifier_or_configured_keywords(self):
        for resource in ("papers", "confnotes", "pubnotes"):
            records = [
                publication(
                    n,
                    resource=resource,
                    group="OTHER",
                    status="Publication Phase Finished"
                    if resource == "papers"
                    else "Phase 1 Finished",
                )
                for n in range(1, 5)
            ]
            key = "referenceCode" if resource == "papers" else "temporaryReferenceCode"
            for n, record in enumerate(records):
                record[key] = f"OTHER-2099-{n:02}"
            records[0][key] = "DEMO-2099-01"
            records[1]["metadata"] = {"gal_keywords": ["INVENTED TOPIC"]}
            records[2]["metadata"] = {"gal_keywords": ["Invented topic suffix"]}
            data = snapshot(analysis(1), **{resource: tuple(records)})
            profile = GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("DEMO",), keywords=("Invented topic",)
                ),
            )
            view = prepare_group(CuratedRegistry(data), profile)
            self.assertEqual(
                {r.reference for r in view.archive}, {records[0][key], records[1][key]}
            )
            self.assertEqual(
                len(prepare_group(CuratedRegistry(data), GroupProfile("DEMO")).archive),
                1,
            )
            with TemporaryDirectory() as folder:
                source = Path(folder) / "input.json"
                source.write_text(json.dumps(data))
                render_group(source, Path(folder) / "out", profile)
                report = json.loads((Path(folder) / "out/view-report.json").read_text())
                self.assertEqual(
                    report["archive_keyword_policy"]["keywords"], ["Invented topic"]
                )
                self.assertFalse((Path(folder) / "out/keyword-survey.md").exists())

    def test_configured_groups_and_subgroups_select_every_publication_type(self):
        for resource in ("papers", "confnotes", "pubnotes"):
            key = "referenceCode" if resource == "papers" else "temporaryReferenceCode"
            records = [
                publication(
                    n,
                    resource=resource,
                    group="OTHER",
                    status="Publication Phase Finished"
                    if resource == "papers"
                    else "Phase 1 Finished",
                )
                for n in range(1, 8)
            ]
            for n, record in enumerate(records):
                record[key] = f"OTHER-2099-{n:02}"
                record["gal_groups"]["leadingSubgroup"] = None
            records[0][key] = "LEGACY-2099-01"
            records[1]["gal_groups"]["leadingGroup"] = "LEGACY"
            records[2]["gal_groups"]["otherGroups"] = ["LEGACY"]
            records[3]["gal_groups"]["leadingSubgroup"] = "OTHER-Merged"
            records[4]["gal_groups"]["subgroups"] = ["OTHER-Merged"]
            records[5]["gal_groups"]["subgroups"] = ["OTHER-Merged-suffix"]
            records[6]["gal_groups"]["leadingGroup"] = "LEGACYX"
            profile = GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("LEGACY",), subgroups=("OTHER-Merged",)
                ),
            )
            view = prepare_group(
                CuratedRegistry(snapshot(analysis(1), **{resource: tuple(records)})),
                profile,
            )
            self.assertEqual(
                {row.reference for row in view.archive},
                {record[key] for record in records[:5]},
            )
            self.assertEqual(len(view.archive), 5)
            trace = next(
                row.provenance["curation"]
                for row in view.archive
                if row.reference == records[4][key]
            )
            self.assertEqual(trace["inputs"]["matching_subgroups"], ["OTHER-Merged"])
            for page in (papers_page(view), confnotes_page(view), pubnotes_page(view)):
                self.assertIn("<dt>Groups</dt><dd><code>LEGACY</code>", page)
                self.assertIn("<dt>Subgroups</dt><dd><code>OTHER-Merged</code>", page)

    def test_configured_affiliations_trace_explicit_analysis_fallback(self):
        own = analysis(1, group="LEGACY")
        own["gal_groups"]["leadingSubgroup"] = "OTHER-Merged"
        paper = publication(1, group=None, related=own["referenceCode"])
        paper["referenceCode"] = "OTHER-2099-01"
        paper["gal_groups"]["leadingSubgroup"] = None
        view = prepare_group(
            CuratedRegistry(snapshot(own, papers=(paper,))),
            GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("LEGACY",), subgroups=("OTHER-Merged",)
                ),
            ),
        )
        self.assertEqual(len(view.archive), 1)
        evidence = view.archive[0].provenance["curation"]["inputs"]
        self.assertEqual(evidence["matching_groups"], ["LEGACY"])
        self.assertEqual(evidence["matching_subgroups"], ["OTHER-Merged"])
        self.assertIn(
            "relatedAnalysis.gal_groups", evidence["affiliation_evidence"]["inputs"]
        )
        self.assertEqual(len(view.ongoing), 0)

    def test_explicit_policy_has_no_implicit_group_and_title_is_publication_only(self):
        import io
        from contextlib import redirect_stdout

        own, foreign = publication(1), publication(2, group="LEGACY")
        foreign["referenceCode"] = "LEGACY-2099-02"
        data = snapshot(analysis(1), papers=(own, foreign))
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "input.json"
            path.write_text(json.dumps(data))
            profile = GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("LEGACY",), title="Invented publication title"
                ),
            )
            view = prepare_group(CuratedRegistry(data), profile)
            self.assertEqual(
                [row.reference for row in view.archive], [foreign["referenceCode"]]
            )
            self.assertEqual(
                len(
                    prepare_group(
                        CuratedRegistry(data),
                        GroupProfile(
                            "DEMO", publication_policy=PublicationPolicy(groups=())
                        ),
                    ).archive
                ),
                0,
            )
            for render in (
                papers_page,
                confnotes_page,
                pubnotes_page,
            ):
                self.assertIn("# Invented publication title", render(view))
            self.assertNotIn("Invented publication title", ongoing_page(view))
            for configured, warn in ((profile, False), (GroupProfile("DEMO"), True)):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    render_group(path, root / "out", configured)
                self.assertEqual("WARNING:" in stdout.getvalue(), warn)

    def test_config_is_optional_and_validated(self):
        from analysis_lister.views.curation import load_publication_policy

        self.assertEqual(load_publication_policy(None, "DEMO"), None)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "curation.toml"
            path.write_text('[groups.DEMO]\nkeywords = ["Invented topic"]\n')
            self.assertEqual(
                load_publication_policy(path, "DEMO"),
                PublicationPolicy(
                    title="", groups=(), subgroups=(), keywords=("Invented topic",)
                ),
            )
            self.assertEqual(load_publication_policy(path, "OTHER"), None)
            path.write_text(
                '[groups.DEMO]\ngroups = ["LEGACY"]\nsubgroups = ["OTHER-Merged"]\n'
            )
            self.assertEqual(
                load_publication_policy(path, "DEMO"),
                PublicationPolicy(
                    groups=("LEGACY",),
                    subgroups=("OTHER-Merged",),
                    title="",
                    keywords=(),
                ),
            )
            path.write_text('[groups.DEMO]\nkeywords = "invalid"\n')
            with self.assertRaises(ValueError):
                load_publication_policy(path, "DEMO")

    def test_cli_loads_keyword_configuration_into_report(self):
        paper = publication(1)
        paper["referenceCode"] = "OTHER-2099-01"
        paper["metadata"] = {"gal_keywords": ["Invented topic"]}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, config, output = (
                root / "input.json",
                root / "curation.toml",
                root / "out",
            )
            source.write_text(json.dumps(snapshot(analysis(1), papers=(paper,))))
            config.write_text(
                '[groups.DEMO]\ntitle = "Invented archive"\ngroups = []\nkeywords = ["Invented topic"]\n'
            )
            cli.main(
                [
                    "render-group",
                    "--group",
                    "DEMO",
                    "--snapshot",
                    str(source),
                    "--output-dir",
                    str(output),
                    "--curation-config",
                    str(config),
                ]
            )
            report = json.loads((output / "view-report.json").read_text())
            self.assertEqual(report["counts"]["archive_publications"], 1)
            self.assertEqual(
                report["profile"]["publication_policy"]["keywords"], ["Invented topic"]
            )
            self.assertIn(
                "<code>Invented topic</code>", (output / "papers.md").read_text()
            )
            self.assertIn(
                "# Invented archive papers", (output / "papers.md").read_text()
            )

    def test_keywords_do_not_select_ongoing_analyses(self):
        own, foreign = analysis(1), analysis(2, group="OTHER")
        foreign["referenceCode"] = "ANA-DEMO-2099-02"
        foreign["metadata"]["gal_keywords"] = ["Invented topic"]
        view = prepare_group(
            CuratedRegistry(snapshot(own, foreign)),
            GroupProfile(
                "DEMO",
                publication_policy=PublicationPolicy(
                    groups=("DEMO",), keywords=("Invented topic",)
                ),
            ),
        )
        self.assertEqual(
            [row.reference for row in view.ongoing], [own["referenceCode"]]
        )


if __name__ == "__main__":
    unittest.main()
