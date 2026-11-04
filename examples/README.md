# Synthetic example

[`synthetic_registry.json`](synthetic_registry.json) contains independently
invented DEMO-2099 records, people, titles, dates and publication metadata. No
private snapshot was used. It follows the current curated schema and is
licensed under GPL-3.0-only. Generated GLANCE links use invented identifiers and
do not identify real records.

After [installation](../README.md#install-and-try-without-credentials), run from
the repository root:

```bash
analysis-lister render-group --group DEMO \
  --snapshot examples/synthetic_registry.json --output-dir pages/demo
```

The [quick start](../README.md#install-and-try-without-credentials) lists the
outputs. The documentation site embeds a working
[analysis card](../docs/ongoing.md#read-an-analysis-card) and
[paper table](../docs/publications.md#read-a-publication-row) from this fixture.
For your own site, enable the [generated browser assets](../docs/rendering.md#enable-browser-assets).

## Expected policy warning

The bundled policies have no `DEMO` entry. This example therefore prints a
missing-policy warning on stdout and selects publications by the `DEMO` token
in their identifiers. It deliberately demonstrates the fallback behaviour.
Use `--curation-config PATH` to supply an
[explicit policy](../docs/rendering.md#publication-policies).

The [README screenshots](../docs/images/README.md) use this same fixture with
an explicit DEMO policy.
