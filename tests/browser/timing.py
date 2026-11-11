# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Wall-clock timings for sequential browser checks and their major phases."""

from contextlib import contextmanager
from time import perf_counter


@contextmanager
def timed(label):
    """Report completion or failure without changing exception propagation."""
    print(f"[timing] START {label}", flush=True)
    start = perf_counter()
    outcome = "FAIL"
    try:
        yield
        outcome = "PASS"
    finally:
        print(f"[timing] {outcome} {label}: {perf_counter() - start:.3f}s", flush=True)
