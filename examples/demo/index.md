# Interactive demo

Explore the four generated pages using the navigation. Each category contains
four independently invented records. External record links are examples and do
not identify real analyses or publications. Search and filtering run locally
in your browser.

The records span different subgroups, keywords, review stages and dates. Papers
include two with DOIs and two submitted papers without DOIs, labelled **Under
review**. Each note collection includes one superseded note and its explicit
replacement; the three non-superseded notes are shown by default.

## Try the filters

Start each example with **Reset filters**.

| Page | What to try | Expected result |
| --- | --- | --- |
| Ongoing analyses | Select **DEMO-Tracking**, then also **DEMO-Calorimetry**. | Two cards, then three. One card belongs to both subgroups and appears only once. |
| Ongoing analyses | With both subgroups selected, search for `Calibration`. | One card: search must also match. Try sorting by review stage and expanding its details. |
| Papers | Select **Under review**, then search for `Tracking`. | Two papers, then one. **Published** selects the two papers with DOIs. |
| Papers | Set **Published before** to January 2099. | One paper from November 2098. Undated submissions do not pass a Before bound. |
| Conference notes | Select **Superseded**, then deselect **Non-superseded**. | All four notes, then only the older superseded note. Expand it to see its replacement link. |
| Public notes | Set **Released after** to June 2099 and **Released before** to August 2099. | One note, released in July. The month bounds are inclusive. |

Search for `Tracking` on any page to find two visible records. You can also
search for an invented contact such as `Aster Example`, or a keyword such as
`Simulation`. These fields are visible in the expanded details.

Titles expand individual records; **Expand all** opens all visible records.
You can also focus a title and press **Enter** or **Space**. Search and filter
choices are stored in the URL, so reloading preserves them. **Reset filters**
restores the default selection. The light/dark switch changes the colour scheme.
