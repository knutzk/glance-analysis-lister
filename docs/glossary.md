# Glossary

[Documentation index](README.md)

These definitions explain how the package uses terms found in GLANCE and the
generated pages. Recorded statuses and dates remain source evidence; they are
not a reconstruction of the full review history.

| Term | Meaning here |
| --- | --- |
| ATLAS | The particle-physics experiment at CERN whose analysis and publication records this package processes. |
| CERN | The European particle-physics laboratory. Live GLANCE access requires an authorised CERN account. |
| GLANCE | ATLAS's system for tracking analyses and publications; the source of the downloaded records. |
| Analysis | An independently identified work record, which can explicitly link to publications. It is not interchangeable with a paper. |
| Paper | A journal-publication record with its own identity, review milestones and publication metadata. |
| CONF note | A conference-note record, rendered on the conference-notes page. |
| PUB note | A public-note record, rendered separately from papers and CONF notes. |
| Main group / subgroup | Recorded affiliations. A record can have a leading assignment and additional assignments. A subgroup name may contain commas. |
| Phase 0, phase 1, phase 2, publication phase | GLANCE process stages whose statuses and milestones are retained where defined by the contract. Missing dates do not establish whether a stage happened. See [ongoing analyses](ongoing.md). |
| Native identifier | The record's identity: `referenceCode` for analyses and papers, `temporaryReferenceCode` for notes. |
| Public identifier | A final publication or note label, which may be recorded directly or derived from explicit public-link evidence. It does not replace native identity. |
| Superseded note | A note with recorded `supersededBy` relationships. It remains in the dataset and can be shown using the note status filter. |
| Published / Under review | Paper filter labels meaning “has a DOI” / “has no DOI”. They are distinct from the full recorded lifecycle status. |
| CDS | CERN Document Server; public record links can help identify notes. |
| DOI | Digital Object Identifier, used for publication links and citation lookup. A synthetic DOI example does not imply a real publication exists. |
| INSPIRE | The public high-energy-physics metadata service queried by the citation resolver. Requests use no GLANCE credentials. |
| SSO | Single sign-on: browser authentication used for live downloads. API and HTML retrieval keep separate credential mechanisms. |
| API snapshot | Saved source data from all four API resources, validated before publication to disk. It is the input for registry construction. |
| Curated registry | Validated, selected and enriched data under the [v2 contract](curated-format.md). It retains independent records but is not a lossless API archive. |
| Prepared view | Collections and decisions ready for a consumer, usable in Python without rendering Markdown. |
| Publication policy | Explicit OR-based group, subgroup and keyword criteria for publication inclusion; separate from ongoing-analysis membership. |
| Provenance | Evidence about where data or decisions came from, including source identifiers, derivations, revisions and content fingerprints. See [provenance](provenance.md). |
| Diagnostic | A reported issue or uncertainty, with evidence and an effect on the view. A diagnostic does not necessarily exclude the record. |
