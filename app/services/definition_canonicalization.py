"""Canonicalisation des définitions déclaratives GH-14."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


_RUNTIME_EXCLUDED_FIELDS = {
    "usage_count",
    "last_test_status",
    "last_validated_at",
    "created_at",
    "updated_at",
}


def _normalize_value(value):
    if isinstance(value, Mapping):
        cleaned = {
            k: _normalize_value(v)
            for k, v in value.items()
            if k not in _RUNTIME_EXCLUDED_FIELDS and v is not None
        }
        return {k: cleaned[k] for k in sorted(cleaned.keys())}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_value(item) for item in value]

    return value


def canonicalize_definition(definition: dict) -> dict:
    """Retourne une version canonique, stable et comparable d'une définition."""
    normalized = _normalize_value(definition)
    return {k: normalized[k] for k in sorted(normalized.keys())}
