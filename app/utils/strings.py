"""Shared string utilities."""

from typing import Iterable


def dedupe_str_list(values: Iterable[str] | None) -> list[str]:
    """Return a deduplicated, whitespace-stripped list preserving insertion order.

    Empty strings and strings that become empty after stripping are dropped.
    Accepts any iterable (list, generator, None).
    """
    if values is None:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        cleaned = raw.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out
