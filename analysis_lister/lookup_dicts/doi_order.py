"""Verified DOI order overrides, keyed by analysis reference code.

Add an entry only after checking the article and corrections. List every DOI
exactly once, original article first, followed by its corrections in order.
Example shape: "TOPQ-YYYY-NN": ["original DOI", "erratum DOI"].
An override that no longer matches the record is an error, not a silent guess.
Immediately above each entry, include a # Source: or # Reason: comment with
the publisher source or an explanation of the evidence for the ordering.
"""

DoiOrder: dict[str, list[str]] = {}
