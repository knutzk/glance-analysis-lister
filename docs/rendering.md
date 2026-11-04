# Rendering and policies

[Documentation index](README.md)

Render a group from a saved curated registry:

```bash
analysis-lister render-group --group TOPQ \
  --snapshot glance_curated_registry.json \
  --output-dir docs/analyses
```

The command writes `ongoing.md`, `papers.md`, `confnotes.md`, `pubnotes.md`,
`view-report.json` and shared browser assets. Without `--output-dir`, it writes to
`pages/group`. Rendering is offline. See [provenance](provenance.md) for output
fingerprints, reproducibility and unchanged-file handling.

## Publication policies

The bundled [`publication-curation.toml`](../publication-curation.toml) controls
publication inclusion. It is used regardless of the working directory. Edit it
to maintain shared policies, or pass `--curation-config PATH` for an alternative.
Each group has its own table:

```toml
[groups.TOPQ]
title = "Top Quark Physics"
groups = ["TOPQ"]
subgroups = []
keywords = []
```

Only a top-level `groups` table is accepted. Each `[groups.NAME]` table accepts
these fields; unknown fields or invalid types fail validation, including in
tables for other groups.

| Field | Type / default when omitted | Meaning |
| --- | --- | --- |
| `title` | Nonempty string / group display title | Publication-page title. |
| `groups` | List of nonempty strings / `[]` | Match an internal identifier's group token (case-insensitive), or an exact leading/additional main-group affiliation. |
| `subgroups` | List of nonempty strings / `[]` | Match an exact leading/additional subgroup name. A name containing a comma remains one string. |
| `keywords` | List of nonempty strings / `[]` | Match an exact label after trimming whitespace and ignoring case. |

Criteria are combined with **OR**: any match includes the publication. These
rules select publications independently of ongoing-analysis membership.

Missing publication affiliations or metadata can be supplied by an explicitly
linked analysis; the report records that derivation. No extra group criterion
is added implicitly. An explicitly empty policy selects no publications.

If a group's table is missing, the command warns on stdout and falls back to
its internal identifier's group token. Define a table even for a group that
selects only its own publications. `title` sets publication-page headings;
`--group-title` sets the ongoing-page heading and supplies the fallback when
the policy omits `title`; without either, headings use the group name. Policy
strings are trimmed, and duplicate criteria are removed when loading.

## Enable browser assets

For output under `docs/analyses`, add these entries to the consuming site's
configuration. Load the common files before the view-specific files:

```yaml
extra_css:
  - analyses/assets/gal-common.css
  - analyses/assets/gal-ongoing.css
  - analyses/assets/gal-papers.css
  - analyses/assets/gal-notes.css
extra_javascript:
  - analyses/assets/gal-common.js
  - analyses/assets/gal-ongoing.js
  - analyses/assets/gal-papers.js
  - analyses/assets/gal-notes.js
```

One asset copy can serve all groups. The controls support Zensical instant
navigation, keyboard operation and dynamically inserted content. Without
JavaScript, all records and details remain readable. Filtering makes no live
requests.

## Read the output

The guides to [ongoing analyses](ongoing.md) and [publication tables](publications.md)
explain the generated views with synthetic examples. Use the
[diagnostic report](diagnostics.md) to understand uncertain states and missing
or conflicting relationships.
