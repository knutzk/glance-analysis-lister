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

![Synthetic ongoing-analysis page with search, subgroup and review-stage controls, and four analysis cards.](docs/images/ongoing.png)

**Publications:** searchable tables for papers, conference notes (CONF) and public
notes (PUB), with date filters and expandable record details.

![Synthetic paper page with search, date and publication-status filters, and four papers, one expanded.](docs/images/papers.png)

[Try the synthetic example](#install-and-try-without-credentials) or read about
[page controls and site integration](docs/rendering.md).

## Install and try without credentials

Start a searchable demo website with independently invented records. Use Python
3.13 and Git in a macOS or Linux shell. Package metadata permits Python 3.13 or
newer; see the [tested environment scope](docs/development.md#supported-validation-scope).

The demo needs **`requirements-docs.txt`**, which installs both the package and
Zensical in the same environment. A package-only `pip install .` does not install
the site preview. These are the same requirements used in the example guide.

```bash
git clone https://github.com/knutzk/glance-analysis-lister.git
cd glance-analysis-lister
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-docs.txt
python scripts/demo.py serve
```

**Open <http://127.0.0.1:8001/>.** The landing page explains the example; use the
navigation to open **Ongoing analyses**, search for `Tracking`, and expand a card.
Try **Papers**, **Conference notes** and **Public notes** next. Stop the server
with **Ctrl+C**.

Run the commands from the cloned repository, whose root contains `scripts/`,
`examples/` and [`zensical-demo.toml`](zensical-demo.toml). The launcher renders
the records, copies the landing page and stylesheet, creates an editable policy
at `pages/demo-policy.toml` on first use, and starts Zensical. Existing policy
edits are preserved. Installation needs internet access; generation and preview
use only local synthetic data.

Already have this checkout and `.venv`? Activate it, run the requirements install
above, then start the launcher. To reopen the demo later, run these from the
repository root:

```bash
source .venv/bin/activate
python scripts/demo.py serve
```

The launcher prepares these files before serving the website:

| Output | Contents |
| --- | --- |
| `pages/demo/index.md` | Demo landing page and suggested interactions. |
| `pages/demo/ongoing.md` | Four invented ongoing analyses at different review stages. |
| `pages/demo/papers.md` | Four invented papers: two with DOIs and two without. |
| `pages/demo/confnotes.md`, `pages/demo/pubnotes.md` | Four invented notes per page; three non-superseded notes shown initially. |
| `pages/demo/assets/` | Browser styles and interaction scripts. |
| `pages/demo/view-report.json` | Selection decisions, provenance and diagnostics. |
| `pages/demo-policy.toml` | Editable copy of the DEMO publication policy. |

Continue with the [policy tutorial](examples/README.md#tutorial-change-publication-selection)
to change what appears in the running demo. It uses this same environment and
these generated files. For your own site, see
[browser asset integration](docs/rendering.md#enable-browser-assets).

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

## Project background

GLANCE analysis lister grew out of the need for a clear, regularly updated
overview of ongoing analyses and recent publications. It brings information
from individual GLANCE records together into searchable group pages.

Initially developed for TOPQ subgroup coordination, its output was subsequently
adopted on the internal TOPQ group website. The project has since become a
general package for ATLAS physics and performance groups, with configurable
group selection and publication policies for Markdown/Zensical websites.
See [rendering and policies](docs/rendering.md).

## Project status and contributing

The declared package version is **0.2.0**; this checkout includes unreleased
changes, and no v1.0 candidate has been qualified. See [compatibility](docs/compatibility.md) for the
defined interface scope and change policy, and
[upgrading](docs/upgrading.md) before replacing a working installation.
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
