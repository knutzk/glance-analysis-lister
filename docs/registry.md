# Curation and identifiers

[Documentation index](README.md)

Curation transforms a saved API snapshot into a validated registry for views and
other consumers. It retains independent records and explicit relationships while
selecting the fields defined by the [curated v2 contract](curated-format.md).
Keep the API snapshot for rebuilding: the curated file is not a lossless archive.

## Field retention and validation

`registry/enrichment.py` contains transformation rules. Its `STRING_LIST_FIELDS`
converts selected named-object collections to names or string lists. Added or
reshaped fields use the `gal_` prefix; source keys are removed after enrichment.
`registry/fields.py` then selects domain fields, including nested relationships,
metadata and DOI/citation entries. DOI/citation pairs stay aligned with their
corrections.

New API fields are excluded until explicitly adopted into the data contract,
independently of any view. The registry retains snapshot and build metadata,
identifier evidence and dictionary hashes for provenance and safe replacement.

The bundled schema validates nested types and dates; separate checks enforce
counts and unique identifiers. Only curated v2 is supported. See the contract's
[compatibility policy](curated-format.md#compatibility-policy) for optional
additions, breaking changes and frozen fixtures.

### Build summaries

`build-registry` reports retained/discarded field counts per resource and
input/output file sizes with their percentage change. Field counts measure
nested object keys after enrichment, including original and derived fields.
They do not measure lost information; all records are retained. Byte sizes
include JSON formatting and build metadata.

## Public links and note identifiers

For published or arXiv-submitted papers, public-page URLs are constructed from
native reference codes. These canonical URLs are marked as derived; the package
does not check page availability.

For notes, a valid API final identifier takes precedence. Otherwise, CONF/PUB
numbers are extracted from API public-page URLs when unambiguous. PUB notes
linked to the CERN Document Server (CDS) can use the bundled
`json/pubnote_identifiers.json` mapping from public CDS record numbers to PUB
identifiers and canonical CDS URLs.

That dictionary preserves public associations from an existing GLANCE export,
including historical detector and technical PUB-note series. It contains no
private analysis identifiers, titles or people. There is no runtime updater or
CDS request.

Release evidence without an identifier produces a diagnostic, not a guessed
number. Derivations are recorded in `gal_publicationProvenance`; curated metadata
records the dictionary hash and source counts.

## Example: keywords before and after curation

An invented API record can contain this metadata fragment:

```json
{
  "metadata": {
    "keywords": [
      {"name": "Invented keyword"},
      {"name": "Second keyword"}
    ]
  }
}
```

The corresponding curated fragment is:

```json
{
  "metadata": {
    "gal_keywords": ["Invented keyword", "Second keyword"]
  }
}
```

The named objects become strings under a `gal_` field. The original `keywords`
field is removed during field selection, and the view uses `gal_keywords` for
search. These are fragments, not complete registries; the
[curated contract](curated-format.md) defines the required container fields.
