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

<table class="gal-screenshot-gallery" role="presentation">
  <tr>
    <td width="50%" valign="top">
      <p><strong>Ongoing analyses</strong></p>
      <a href="docs/images/ongoing.png"><img src="docs/images/ongoing.png" width="360" alt="Synthetic ongoing-analysis page with search, subgroup and review-stage controls, and four analysis cards."></a>
      <p>Searchable cards with affiliations, review progress and expandable details.</p>
    </td>
    <td width="50%" valign="top">
      <p><strong>Publications</strong></p>
      <a href="docs/images/papers.png"><img src="docs/images/papers.png" width="360" alt="Synthetic paper page with search, date and publication-status filters, and four papers, one expanded."></a>
      <p>Tables for papers, conference notes and public notes, with date filters and expandable details.</p>
    </td>
  </tr>
</table>

Select a screenshot to open it at full size.

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

mkdir -p examples/demo/work
cp examples/demo/zensical.toml examples/demo/work/zensical.toml
cp examples/demo/publication-curation.toml examples/demo/work/demo-policy.toml

analysis-lister render-group --group DEMO --group-title "Synthetic demo" \
  --snapshot examples/synthetic_registry.json \
  --curation-config examples/demo/work/demo-policy.toml \
  --output-dir examples/demo/work/pages

cp examples/demo/index.md examples/demo/work/pages/index.md
cp docs/stylesheets/site.css examples/demo/work/pages/assets/site.css

python -m zensical serve -f examples/demo/work/zensical.toml --dev-addr 127.0.0.1:8001
```

**Open <http://127.0.0.1:8001/>.** The landing page explains the example; use the
navigation to open **Ongoing analyses**, search for `Tracking`, and expand a card.
Try **Papers**, **Conference notes** and **Public notes** next. Stop the server
with **Ctrl+C**.

Run all commands from the cloned repository root. The standalone demo's
configuration, landing page and policy live in [`examples/demo/`](examples/demo/);
the root `zensical.toml` configures the full package documentation site.
The commands above create an editable policy copy, render the four pages,
copy the local site configuration, landing page and stylesheet,
and start Zensical. Installation needs internet access; rendering and preview
use only local synthetic data.

Already have this checkout and `.venv`? Activate it and start with the requirements
install above. The setup's `cp` commands reset the local configuration and policy; to keep
your edits, rerun only the render command or reopen the existing site below.
To reopen an already-generated demo, run only these from the repository root:

```bash
source .venv/bin/activate
python -m zensical serve -f examples/demo/work/zensical.toml --dev-addr 127.0.0.1:8001
```

The setup produces:

| Output | Contents |
| --- | --- |
| `examples/demo/work/pages/index.md` | Demo landing page and suggested interactions. |
| `examples/demo/work/pages/ongoing.md` | Four invented ongoing analyses at different review stages. |
| `examples/demo/work/pages/papers.md` | Four invented papers: two with DOIs and two without. |
| `examples/demo/work/pages/confnotes.md`, `examples/demo/work/pages/pubnotes.md` | Four invented notes per page; three non-superseded notes shown initially. |
| `examples/demo/work/pages/assets/` | Browser styles and interaction scripts. |
| `examples/demo/work/pages/view-report.json` | Selection decisions, provenance and diagnostics. |
| `examples/demo/work/demo-policy.toml` | Editable copy of the DEMO publication policy. |
| `examples/demo/work/zensical.toml` | Editable site configuration, shared by Demo and added groups. |

Continue with the [policy tutorial](examples/README.md#tutorial-change-publication-selection)
to change what appears in the running demo. It uses this same environment and
these generated files. For your own site, see
[browser asset integration](docs/rendering.md#enable-browser-assets).

## Add CERN ATLAS data to the same demo

Continue in the **same checkout and environment**, using the same demonstrator.
The synthetic **Demo** stays available; TOPQ will appear alongside it.
Stop Zensical with **Ctrl+C** before changing its navigation.

With an authorised CERN account, first download the accessible records:

```bash
analysis-lister download-api --login
```

`--login` opens browser sign-in; omit it on later downloads to reuse stored
credentials. This writes `glance_api_registry.json` in the repository root.
Next, build the curated registry and render TOPQ into the demonstrator:

```bash
analysis-lister build-registry
analysis-lister render-group --group TOPQ \
  --snapshot glance_curated_registry.json \
  --output-dir examples/demo/work/pages/topq
```

`build-registry` writes `glance_curated_registry.json`. If you already have that
curated registry, start at `render-group`. The renderer uses the bundled TOPQ
publication policy; see [publication policies](docs/rendering.md#publication-policies)
to customise selection or use another group.

In **`examples/demo/work/zensical.toml`**, replace the `nav = [...]` block
under `[project]` with:

```toml
nav = [
  { "Demo" = [
    { "Overview" = "index.md" },
    { "Ongoing analyses" = "ongoing.md" },
    { "Papers" = "papers.md" },
    { "Conference notes" = "confnotes.md" },
    { "Public notes" = "pubnotes.md" },
  ] },
  { "TOPQ (CERN data)" = [
    { "Ongoing analyses" = "topq/ongoing.md" },
    { "Papers" = "topq/papers.md" },
    { "Conference notes" = "topq/confnotes.md" },
    { "Public notes" = "topq/pubnotes.md" },
  ] },
]
```

Start the **same preview command** again:

```bash
python -m zensical serve -f examples/demo/work/zensical.toml --dev-addr 127.0.0.1:8001
```

**Open <http://127.0.0.1:8001/> and select TOPQ (CERN data).** Demo and TOPQ
now share one site, with the same search, filter and navigation controls.
Rerendering into `examples/demo/work/pages/topq/` updates TOPQ without replacing
the synthetic pages. The local configuration, generated pages and built HTML
stay under the ignored `examples/demo/work/` directory.

Keep this local site private: it now contains CERN data, including generated
reports. Keep real snapshots and cookies private too. The package's public
documentation build excludes this working directory.

For an existing website, see [integration into a consuming site](docs/rendering.md#integrate-into-a-consuming-site).
For recovery or other command options, see [commands, downloads and recovery](docs/workflows.md)
and `analysis-lister COMMAND --help`.

## How it fits together

The three numbered boxes are `analysis-lister` commands. **`refresh` runs steps 1–3 in
order**; previewing the result is a separate step.

![GLANCE feeds three refresh commands: download-api writes an API snapshot, build-registry writes a curated registry, and render-group produces Markdown pages, assets and a report. The flow then turns right to a preview or website.](docs/images/command-flow.svg)

To run the same three stages yourself, execute these commands in the same
directory, in order:

```bash
analysis-lister download-api --login
analysis-lister build-registry
analysis-lister render-group --group TOPQ --output-dir examples/demo/work/pages/topq
```

The default filenames connect the steps: `download-api` writes
`glance_api_registry.json`; `build-registry` reads it and writes
`glance_curated_registry.json`; `render-group` reads that registry. Only the
download needs CERN access. Once you have a snapshot, you can start at the
corresponding later step: rebuild after curation changes, or just render again
after changing the group or publication policy.

As an alternative to running those three commands separately, the combined command is
`analysis-lister refresh --groups TOPQ --output-dir examples/demo/work/pages/topq --login`.
After adding TOPQ to the demonstrator navigation above, use the same Zensical
preview command to view updates.

Other commands handle [CSV exports, comparisons and citation maintenance](docs/workflows.md#where-the-other-commands-fit).
For the internal layers and prepared Python views, see [architecture](docs/architecture.md).

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
