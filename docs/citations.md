# Citations

[Documentation index](README.md)

Citation commands update the bundled `json/doi_metadata.json` dictionary by
default, regardless of the working directory. They do not create a local copy.
Use `--doi-cache PATH` to select another store; a missing custom store starts
empty. Stores are loaded for each operation, not on import. Entries require
`citation` and `source`; optional fields are `material`, `resolved_at`,
`source_url` and `inspire_id`. Material labels distinguish publications, errata,
addenda and editorial notes.

## Resolve citations

Use a saved API snapshot or curated registry:

```bash
analysis-lister resolve-dois --snapshot glance_api_registry.json --method infer
analysis-lister resolve-dois --snapshot glance_api_registry.json --method inspire
```

| Method | Behaviour |
| --- | --- |
| `infer` | Recognises fully specified JHEP citations offline. |
| `inspire` | Queries public INSPIRE metadata. |
| `auto` | Tries inference first. |

Supply repeated `--doi` arguments instead of `--snapshot` to select individual
DOIs. `--limit 10` limits attempts; `--refresh-existing` revisits non-manual
entries. Entries with `source = "manual"` are protected from automatic
replacement. There is no separate lock setting.

Public metadata requests use a separate session without GLANCE credentials,
with verified TLS, bounded retries and rate limiting. Each successful result is
saved atomically. Ambiguous associations remain unresolved and can be retried.

## Format citations and update pages

Normalise cached journal names and starting pages offline:

```bash
analysis-lister format-citations
```

Manual entries are left unchanged. After editing, resolving or formatting
citations, run `build-registry` to embed them in the registry, then `render-group`
to update the pages. Citation commands do not rewrite snapshots. Run commands
that write the same dictionary sequentially.

## DOI extraction and correction ordering

DOIs come from URL fields in the API's final journal publication links. DOI
resolver URLs and publisher URLs containing a DOI are supported. Link labels
are ignored, and publisher identifiers such as ScienceDirect PIIs are not
converted to DOIs.

A uniquely identified original publication is listed before its corrections.
Corrections use DOI-encoded dates when those establish an order; otherwise their
relative input order is retained. If neither material labels nor dates identify
an original publication, ambiguous ordering produces a warning.

## Example: infer a citation without a network request

This invented DOI exercises the JHEP pattern. Use a separate temporary store to
leave the bundled dictionary untouched:

```bash
analysis-lister resolve-dois --doi '10.1007/JHEP07(2099)999' \
  --method infer --doi-cache /tmp/demo-citations.json
```

The stored citation is `JHEP 07 (2099) 999`, with source `doi-pattern:jhep`.
Inference formats a recognised pattern; it does not verify that a publication
exists. This DOI and citation are fictional.
