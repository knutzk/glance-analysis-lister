# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""CONF and PUB note tables, people, supersession and details."""

import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import (
    confnotes_page,
    pubnotes_page,
)
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[1]


class ConfNoteTableTests(unittest.TestCase):
    def test_conf_note_row_has_only_requested_columns_and_public_identifier(self):
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["phase1"]["draftCdsUrl"] = "https://cds.cern.ch/record/209900000001"
        note["gal_groups"]["leadingSubgroup"] = "DEMO-Alpha"
        note["gal_groups"]["subgroups"] = ["DEMO-Beta"]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        self.assertEqual(
            [th.text for th in soup.select("thead th")],
            ["Identifier", "Title", "Release date"],
        )
        row = soup.select_one("tbody tr")
        cells = row.select(":scope > td, :scope > th")
        self.assertEqual(len(cells), 3)
        self.assertEqual(
            [link.text for link in cells[0].select("a")],
            [
                note.get("finalReferenceCode") or note.get("gal_finalReferenceCode"),
                "CDS",
            ],
        )
        self.assertIn(note["temporaryReferenceCode"], cells[0].a["href"])
        self.assertEqual(cells[0].select("a")[1]["href"], note["phase1"]["draftCdsUrl"])
        self.assertEqual(cells[0].a.text, note["finalReferenceCode"])
        self.assertNotIn(note["temporaryReferenceCode"], row.get_text())
        self.assertEqual(cells[1].text, note["shortTitle"])
        self.assertEqual(cells[2].text, note["phase1"]["releaseDate"])
        self.assertFalse(
            soup.select(
                "[data-gal-disclosure], details, .gal-publication-details__body, [data-gal-pagination]"
            )
        )
        self.assertFalse(soup.select('[data-gal-filter="subgroups"]'))
        self.assertIsNotNone(soup.select_one("[data-gal-search]"))
        self.assertTrue(soup.select_one("[data-gal-note-controls]").has_attr("hidden"))
        self.assertFalse(row.has_attr("hidden"))
        evidence = next(
            r for r in view.archive if r.resource == "confnotes"
        ).provenance["details"]["inputs"]["cds_record"]
        self.assertEqual(evidence["rule"], "conf-note-cds-record")

    def test_missing_cds_link_is_blank_without_guessing_a_record(self):
        from analysis_lister.views.notes import note_cds_record

        for value in (
            None,
            "",
            "javascript:alert(1)",
            "https://example.test/record/1",
            "https://cds.cern.ch/not-a-record",
        ):
            self.assertIsNone(
                note_cds_record({"phase1": {"draftCdsUrl": value}}, "confnotes").value
            )
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        self.assertEqual(
            [
                a.text
                for a in soup.select_one("[data-gal-note]").select("th:first-child a")
            ],
            [note["finalReferenceCode"]],
        )


class ConfNoteExpansionTests(unittest.TestCase):
    def test_people_and_tags_are_rendered_without_review_dates(self):
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["gal_analysisContacts"] = ["Invented Contact"]
        note["gal_groups"].update(
            {"leadingSubgroup": "DEMO-Alpha", "subgroups": ["DEMO-Beta"]}
        )
        note["phase1"].update(
            {
                "gal_editorialBoard": ["Invented Member"],
                "gal_editorialBoardChairs": ["Invented Chair"],
                "firstSignOffDate": "2099-01-03T10:00:00Z",
            }
        )
        note["metadata"] = {
            "gal_keywords": ["Invented keyword"],
            "gal_statisticalTools": ["Invented tool"],
            "mvaMlTools": [{"name": "Invented ML tool"}],
            "collisions": [{"year": "2099", "ecmValue": "13", "ecmUnit": "TeV"}],
        }
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        detail = soup.select_one("[data-gal-note-details]")
        self.assertEqual(detail.td["colspan"], "3")
        self.assertIn("Invented Chair (chair)", detail.get_text())
        self.assertIn("Invented Contact", detail.get_text())
        self.assertIn("Not recorded", detail.get_text())
        self.assertNotIn("2099-01-03", detail.get_text())
        self.assertEqual(
            [tag.text for tag in detail.select(".gal-note-tags .gal-badge")],
            ["Invented keyword", "Invented tool", "Invented ML tool", "2099 · 13 TeV"],
        )
        self.assertEqual(
            [
                tag.contents[0]
                for tag in detail.select(".gal-card__affiliations .gal-badge--leading")
            ],
            ["DEMO", "DEMO-Alpha"],
        )
        self.assertIn("DEMO-Beta", detail.get_text())
        self.assertTrue(
            detail.select_one("[data-gal-note-collapse]").has_attr("hidden")
        )
        self.assertFalse(detail.has_attr("hidden"))  # Complete static fallback.
        prepared = next(row for row in view.archive if row.resource == "confnotes")
        self.assertEqual(
            prepared.provenance["details"]["inputs"]["conf_note_expansion"]["rule"],
            "conf-note-expansion",
        )


class ConfNoteResponsibleNameTests(unittest.TestCase):
    def test_scalar_responsibles_and_chairs_are_names_not_characters(self):
        from analysis_lister.views.notes import note_expansion

        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["phase1"].update(
            {
                "gal_firstSignOffResponsible": "Invented First Person",
                "gal_secondSignOffResponsible": [
                    "Invented Second Person",
                    "Invented Third Person",
                ],
                "gal_editorialBoard": "Invented Board Member",
                "gal_editorialBoardChairs": "Invented Chair",
            }
        )
        decision = note_expansion(note, "confnotes")
        people = {
            person["label"]: person["names"] for person in decision.value["people"]
        }
        self.assertEqual(
            people["First sign-off responsible"], ["Invented First Person"]
        )
        self.assertEqual(
            people["Second sign-off responsible"],
            ["Invented Second Person", "Invented Third Person"],
        )
        self.assertEqual(
            people["Editorial board"],
            ["Invented Board Member", "Invented Chair (chair)"],
        )
        self.assertEqual(
            decision.inputs["phase1.gal_firstSignOffResponsible"],
            "Invented First Person",
        )
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        markup = (
            BeautifulSoup(confnotes_page(view), "html.parser")
            .select_one("[data-gal-note-details]")
            .get_text()
        )
        self.assertIn("Invented First Person", markup)
        self.assertNotIn("I, n, v, e, n", markup)


class ConfNoteSupersessionTests(unittest.TestCase):
    def test_explicit_links_classify_released_notes_without_target_resolution(self):
        current = publication(1, resource="confnotes", status="Phase 1 Finished")
        superseded = publication(2, resource="confnotes", status="Phase 1 Finished")
        superseded["supersededBy"] = [
            {"type": "Paper", "referenceCode": "DEMO-2099-77"}
        ]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(current, superseded))),
            GroupProfile("DEMO"),
        )
        rows = {
            row.reference: row for row in view.archive if row.resource == "confnotes"
        }
        self.assertFalse(
            rows[current["temporaryReferenceCode"]].details.conf_note.superseded
        )
        self.assertTrue(
            rows[superseded["temporaryReferenceCode"]].details.conf_note.superseded
        )
        self.assertTrue(all(row.state == "released" for row in rows.values()))
        evidence = rows[superseded["temporaryReferenceCode"]].provenance["details"][
            "inputs"
        ]["conf_note_expansion"]["inputs"]["supersession"]
        self.assertEqual(evidence["rule"], "conf-note-supersession")
        self.assertEqual(evidence["inputs"]["supersededBy"], superseded["supersededBy"])
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        self.assertEqual(
            soup.select_one('[data-gal-note-supersession="non-superseded"]')[
                "aria-pressed"
            ],
            "true",
        )
        self.assertEqual(
            soup.select_one('[data-gal-note-supersession="superseded"]')[
                "aria-pressed"
            ],
            "false",
        )
        self.assertEqual(soup.select_one("[data-gal-note-count]").text, "2 of 2 notes")
        self.assertEqual(
            len(soup.select('[data-gal-note][data-gal-superseded="true"]')), 1
        )
        self.assertFalse(
            any(row.has_attr("hidden") for row in soup.select("[data-gal-note]"))
        )


class ConfNoteSupersedingLinksTests(unittest.TestCase):
    def test_superseding_links_use_explicit_native_targets_even_if_absent(self):
        note = publication(1, resource="confnotes", status="Phase 1 Finished")
        note["supersededBy"] = [
            {"type": "Paper", "referenceCode": "DEMO-2099-77"},
            {"type": "CONF note", "referenceCode": "CONF-DEMO-2099-88"},
            {"type": "Analysis", "referenceCode": "ANA-DEMO-2099-99"},
        ]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(confnotes_page(view), "html.parser")
        links = soup.select(".gal-note-superseders a")
        self.assertEqual(len(links), 3)
        for link, target, resource in zip(
            links,
            note["supersededBy"],
            ["papers", "confnotes", "analyses"],
            strict=True,
        ):
            self.assertIn("/" + resource + "/details.php?", link["href"])
            self.assertIn(target["referenceCode"], link["href"])
            self.assertIn(target["referenceCode"], link.text)
        current = publication(2, resource="confnotes", status="Phase 1 Finished")
        current_view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), confnotes=(current,))),
            GroupProfile("DEMO"),
        )
        self.assertFalse(
            BeautifulSoup(confnotes_page(current_view), "html.parser").select(
                ".gal-note-superseders"
            )
        )


class PubNotePageTests(unittest.TestCase):
    def test_pub_notes_share_note_controls_and_use_public_identifiers_and_readers(self):
        note = publication(1, resource="pubnotes", status="Phase 1 Finished")
        note["gal_finalReferenceCode"] = note.pop("finalReferenceCode")
        note["gal_groups"]["leadingSubgroup"] = "DEMO-Alpha"
        note["phase1"].update(
            {
                "draftCdsUrl": "https://cds.cern.ch/record/209900000001",
                "gal_readers": ["Invented Reader"],
                "gal_firstReaders": "Invented First Reader",
                "gal_secondReaders": [],
            }
        )
        note["supersededBy"] = [{"type": "Paper", "referenceCode": "DEMO-2099-77"}]
        view = prepare_group(
            CuratedRegistry(snapshot(analysis(1), pubnotes=(note,))),
            GroupProfile("DEMO"),
        )
        soup = BeautifulSoup(pubnotes_page(view), "html.parser")
        summary = soup.select_one("[data-gal-note]")
        cells = summary.select(":scope > td, :scope > th")
        self.assertEqual(len(cells), 3)
        self.assertEqual(cells[0].a.text, "ATL-PHYS-PUB-2099-001")
        self.assertNotIn(note["temporaryReferenceCode"], summary.get_text())
        self.assertIn("/pubnotes/details.php?", cells[0].a["href"])
        self.assertEqual(
            [link.text for link in cells[0].select("a")],
            [
                note.get("finalReferenceCode") or note.get("gal_finalReferenceCode"),
                "CDS",
            ],
        )
        details = soup.select_one("[data-gal-note-details]")
        self.assertIn("Invented Reader", details.get_text())
        self.assertIn("Invented First Reader", details.get_text())
        self.assertIn("Second readers", details.get_text())
        self.assertIn("Not recorded", details.get_text())
        self.assertNotIn("Editorial board", details.get_text())
        self.assertTrue(details.select(".gal-note-superseders a"))
        self.assertTrue(details.select("[data-gal-note-collapse]"))
        self.assertTrue(soup.select("[data-gal-note-supersession]"))
        self.assertEqual(soup.select_one("[data-gal-note-count]").text, "1 of 1 notes")
        row = next(row for row in view.archive if row.resource == "pubnotes")
        self.assertEqual(
            row.provenance["details"]["inputs"]["pub_note_expansion"]["rule"],
            "pub-note-expansion",
        )
        self.assertEqual(
            row.provenance["details"]["inputs"]["cds_record"]["rule"],
            "pub-note-cds-record",
        )


if __name__ == "__main__":
    unittest.main()
