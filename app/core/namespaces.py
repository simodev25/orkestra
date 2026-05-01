"""Namespace constants and validation helpers."""

from __future__ import annotations

import re
from uuid import UUID


DEFAULT_NAMESPACE_ID = UUID("b536d855-6f6a-573c-8a75-99d5631a91f9")
DEFAULT_NAMESPACE_SLUG = "default"
DEFAULT_NAMESPACE_NAME = "Default"
DEFAULT_NAMESPACE_DESCRIPTION = "System default namespace"

# RFC1123/DNS-label style slug: lowercase alnum + hyphen, no leading/trailing hyphen.
# Rust regex engine used by pydantic-core does not support lookarounds.
NAMESPACE_SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
NAMESPACE_SLUG_RE = re.compile(NAMESPACE_SLUG_PATTERN)
