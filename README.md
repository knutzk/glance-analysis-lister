# GLANCE analysis lister

GLANCE analysis lister turns ATLAS records into searchable pages for a physics
group: ongoing analyses, papers, conference notes and public notes. Group members
can follow reviews, find publications and explore the details of each record.

GLANCE is the system the ATLAS experiment at CERN uses to track this work.
Downloading its records requires authorised CERN access. Once saved, the data
can be curated and rendered offline without authentication or a database. The
included synthetic example lets you try the package without CERN access.

## What the pages look like

These screenshots show **fictional example records** rendered in a Zensical site.

**Ongoing analyses:** searchable cards with affiliations, review progress and
expandable details.

![Synthetic ongoing-analysis page with search, subgroup and review-stage controls, and one analysis card.](docs/images/ongoing.png)

**Publications:** searchable tables for papers, conference notes (CONF) and public
notes (PUB), with date filters and expandable record details.

![Synthetic paper page with search, date and publication-status filters, and one expanded paper.](docs/images/papers.png)

[Try the synthetic example](#install-and-try-without-credentials) or read about
[page controls and site integration](docs/rendering.md).

## Install and try without credentials

Use Python 3.13 and Git. Package metadata permits Python 3.13 or newer; CI tests
3.13. Run these commands in a macOS or Linux shell:

```bash
git clone https://github.com/knutzk/glance-analysis-lister.git
cd glance-analysis-lister
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install .
analysis-lister render-group --group DEMO --group-title "Synthetic demo" \
  --snapshot examples/synthetic_registry.json \
  --curation-config examples/demo/publication-curation.toml --output-dir pages/demo
```

Installation needs internet access; rendering the example runs offline.
You can use `python -m analysis_lister` in place of `analysis-lister`.

The command writes:

| Output under `pages/demo/` | Contents |
| --- | --- |
| `ongoing.md` | One invented ongoing analysis. |
| `papers.md` | One invented paper. |
| `confnotes.md`, `pubnotes.md` | One invented note on each page. |
| `assets/` | Shared CSS and JavaScript for styling and interaction. |
| `view-report.json` | Selection decisions, provenance and diagnostics. |

The explicit DEMO policy selects the invented publications without a missing-policy
warning. Follow the [synthetic example](examples/README.md) to preview the complete
site and try changing its publication policy.

Try the live [analysis card](docs/ongoing.md#read-an-analysis-card) and
[publication table](docs/publications.md#read-a-publication-row) in the
documentation site. To use your generated pages in another Zensical site,
[enable the browser assets](docs/rendering.md#enable-browser-assets).

## Refresh pages from GLANCE

With an authorised CERN account, run this from the repository that will use the
pages. `--login` opens browser sign-in:

```bash
analysis-lister refresh --groups TOPQ --output-dir docs/analyses --login
```

This downloads the accessible records, builds a curated registry and renders the
four group pages. Omit `--login` on later runs to reuse stored credentials.
Snapshots default to `glance_api_registry.json` and
`glance_curated_registry.json` in the calling directory. Keep real snapshots,
cookies, diagnostic reports and pages containing non-public records private.

If a stage fails, completed stages remain. See
[commands, downloads and recovery](docs/workflows.md) to resume from saved data,
choose destinations or refresh several groups. Use `analysis-lister COMMAND --help`
for available options.

## How it fits together

```text
GLANCE → validated API snapshot → curated registry → prepared views
                                                        ↓
                                            Markdown, assets, reports
```

The stages are separate: you can rebuild from a saved API snapshot, render an
existing registry, or use prepared collections directly in Python. See
[architecture](docs/architecture.md) for the code layout and the
[documentation index](docs/README.md) for policies, citations, data contracts
and other workflows.

## Project status and contributing

The package is at **0.2.0**; v1.0 compatibility promises are not yet finalized.
Offline and browser checks use
synthetic data; live CERN authentication needs separate validation.

See [development and validation](docs/development.md) for setup and checks.
Use independently invented fixtures when contributing. To edit or preview these
guides, follow the [local site guide](docs/site.md).

## AI assistance disclosure

Parts of this codebase were developed with AI assistance from Codex (OpenAI)
and Claude (Anthropic). All output was reviewed and validated by the author.

## Licence

Copyright © 2024–2026 Knut Zoch. Licensed under
[GNU GPL version 3](LICENCE), `GPL-3.0-only`.

Maintainer: [Knut Zoch](https://github.com/knutzk).
