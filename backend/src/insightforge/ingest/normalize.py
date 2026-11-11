"""Column-name and identifier normalization."""

from __future__ import annotations

import re

import pyarrow as pa

_IDENT_RE = re.compile(r"[^a-z0-9_]+")
RESERVED = {
    "select", "from", "where", "table", "order", "group", "by", "limit", "join", "union",
    "user", "default", "all", "and", "or", "not", "null", "as", "on", "case", "when",
}  # fmt: skip


def to_identifier(raw: str, fallback: str = "t") -> str:
    """Lower-case SQL identifier matching ``[a-z_][a-z0-9_]{0,62}``."""
    s = _IDENT_RE.sub("_", raw.strip().lower()).strip("_")
    s = re.sub(r"_+", "_", s)
    if not s:
        s = fallback
    if s[0].isdigit():
        s = f"{fallback}_{s}"
    if s in RESERVED:
        s = f"{s}_"
    return s[:63]


def unique_identifier(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    i = 2
    while f"{base[:58]}_{i}" in taken:
        i += 1
    return f"{base[:58]}_{i}"


def normalize_columns(table: pa.Table) -> pa.Table:
    """Trim, de-blank and de-duplicate column names, preserving readable original text."""
    seen: set[str] = set()
    names = []
    for i, name in enumerate(table.column_names):
        clean = " ".join(str(name).split()) or f"column_{i + 1}"
        if clean.lower().startswith("unnamed:"):
            clean = f"column_{i + 1}"
        candidate, n = clean, 2
        while candidate.lower() in seen:
            candidate = f"{clean}_{n}"
            n += 1
        seen.add(candidate.lower())
        names.append(candidate)
    return table.rename_columns(names)
