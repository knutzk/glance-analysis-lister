# Add CERN data to the demo

[Documentation index](README.md)

First run the [synthetic quick start](../README.md#install-and-try-without-credentials).
This guide adds real TOPQ pages alongside Demo in the **same standalone site**.
Keep the same checkout and environment, and run all commands from the repository
root with its `.venv` activated. The synthetic **Demo** stays available.
Stop Zensical with **Ctrl+C** before changing its navigation.

**TOPQ is an example choice, not a requirement.** Use your own ATLAS physics or
performance group instead. For example, to use HIGP throughout this guide:

- Replace `TOPQ` with `HIGP` in `--group`, `--groups` and the navigation label.
- Replace the `topq` output subdirectory and navigation paths with `higp`.

The directory name is your choice; the navigation paths must match it. Download
and registry construction are shared across groups, so those commands stay the
same. Check the publication policy for your chosen group; use
`--curation-config PATH` with `render-group` or `refresh` to supply your own.

## Download the records

With an authorised CERN account, first download the accessible records:

```bash
analysis-lister download-api --login
```

`--login` opens browser sign-in; omit it on later downloads to reuse stored
credentials. This writes `glance_api_registry.json` in the repository root.

## Build and render TOPQ

Build the curated registry and render TOPQ into the demonstrator:

```bash
analysis-lister build-registry
analysis-lister render-group --group TOPQ \
  --snapshot glance_curated_registry.json \
  --output-dir examples/demo/work/pages/topq
```

`build-registry` writes `glance_curated_registry.json`. If you already have that
curated registry, start at `render-group`. The renderer uses the bundled TOPQ
publication policy; see [publication policies](rendering.md#publication-policies)
to customise selection or use another group.

## Add TOPQ to the navigation

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

## Next steps

To update all three stages in one command, use
`analysis-lister refresh --groups TOPQ --output-dir examples/demo/work/pages/topq --login`
and omit `--login` when reusing stored credentials. See
[how the commands connect](workflows.md#how-the-commands-connect) for saved-file
handoffs and rerunning individual stages.

For an existing website, see [integration into a consuming site](rendering.md#integrate-into-a-consuming-site).
For recovery or other command options, see [commands, downloads and recovery](workflows.md)
and `analysis-lister COMMAND --help`.
