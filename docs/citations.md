# Citations

[Documentation index](README.md)

`resolve-dois` and `format-citations` require **`--doi-cache PATH`**. Choose a
writable store outside the package installation so your updates survive upgrades.
There is no implicit write destination or per-user cache. Stores are loaded for
each operation, not on import.

`build-registry` and `refresh` read the bundled `json/doi_metadata.json` by default,
regardless of the working directory. Pass `--doi-cache PATH` to make them read
your maintained store. Every explicit path selects exactly that file: a missing
file starts empty, even if named `json/doi_metadata.json`. There is no automatic
merge with bundled entries.

## Choose a store

To start with the bundled citations, copy them from a matching source checkout
or source archive. For a new store, run from that source root:

```bash
mkdir -p data
cp json/doi_metadata.json data/doi-metadata.json
```

If you already maintain a store, keep it and use its path instead. Resolver
updates are saved atomically; formatting writes only when an entry changes.
Keep a backup of your edits. Upgrading the package does not migrate or merge
this external file with newer bundled citations.

Maintainers can deliberately update the tracked dictionary by passing
`--doi-cache json/doi_metadata.json` from the checkout. Review those public
metadata changes before committing them. An installed package's shared data
directory is not a durable location for user updates.

## DOI metadata JSON

The store is a JSON object keyed by normalised, lowercase DOIs. This example
uses invented DOIs, citations and dates:

```json
{
  "10.1007/jhep07(2099)999": {
    "citation": "JHEP 07 (2099) 999",
    "source": "doi-pattern:jhep",
    "resolved_at": "2099-03-01T12:00:00+00:00"
  },
  "10.9999/synthetic": {
    "citation": "Invented journal citation",
    "source": "manual",
    "material": "publication"
  }
}
```

Each record requires `citation` and `source`. The first records an inferred
citation and when it was resolved; the second is protected from automatic
replacement because its source is `manual`. Optional fields are `material`,
`resolved_at`, `source_url` and `inspire_id`. Material labels distinguish
publications, errata, addenda and editorial notes.

## Resolve citations

Use a saved API snapshot or curated registry:

```bash
analysis-lister resolve-dois --snapshot glance_api_registry.json \
  --method infer --doi-cache data/doi-metadata.json
analysis-lister resolve-dois --snapshot glance_api_registry.json \
  --method inspire --doi-cache data/doi-metadata.json
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
analysis-lister format-citations --doi-cache data/doi-metadata.json
```

Manual entries are left unchanged. After editing, resolving or formatting
citations, run `build-registry --doi-cache data/doi-metadata.json` to embed them
in the registry, then `render-group`
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
