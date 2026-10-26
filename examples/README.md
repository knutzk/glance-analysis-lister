# Synthetic curated registry

`synthetic_registry.json` contains independently invented DEMO-2099 records,
people, titles, dates and publication metadata. No private snapshot was used.
The example uses the current curated schema and is distributed under GPL-3.0-only.

```bash
analysis-lister render-group --group DEMO --snapshot examples/synthetic_registry.json --output-dir pages/demo
```

Missing publication curation configuration intentionally demonstrates the stdout
warning and group-token fallback. Supply `--curation-config` for an explicit policy.
GLANCE URLs constructed from invented identifiers do not identify real records.
