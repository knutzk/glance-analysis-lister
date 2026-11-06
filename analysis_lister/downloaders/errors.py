# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Safe endpoint labels and HTTP remedies, without response text or credentials."""

from urllib.parse import urlsplit, urlunsplit


def endpoint_label(url):
    """Show the service endpoint without URL credentials, query or fragment."""
    try:
        parts = urlsplit(str(url))
        if not parts.scheme or not parts.netloc:
            return "configured endpoint"
        return urlunsplit(
            (parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", "")
        )
    except ValueError:
        return "configured endpoint"


def http_failure(status):
    """Use only a numeric status; upstream reason phrases can contain payloads."""
    if type(status) is not int or not 100 <= status <= 599:
        return "HTTP request failed; check the configured endpoint and service availability."
    if status == 401:
        remedy = "authentication was rejected; retry with --login."
    elif status == 403:
        remedy = "access was denied; check your account's GLANCE permissions."
    elif status == 404:
        remedy = "endpoint was not found; check the configured endpoint and client compatibility."
    elif status == 429:
        remedy = "request rate was limited; wait before retrying."
    elif status >= 500:
        remedy = "service failed; retry after the service recovers."
    else:
        remedy = (
            "request failed; check the configured endpoint and client compatibility."
        )
    return f"HTTP {status}: {remedy}"
