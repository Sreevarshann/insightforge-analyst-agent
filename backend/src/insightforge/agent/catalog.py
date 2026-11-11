"""Compact, profile-derived dataset descriptions given to the planner."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from insightforge.db.models import Dataset


def build_catalog(db: Session, dataset_ids: list[str] | None = None) -> list[dict[str, Any]]:
    out = []
    stmt = select(Dataset).order_by(Dataset.created_at)
    for ds in db.scalars(stmt):
        if dataset_ids and ds.id not in dataset_ids:
            continue
        cur = ds.current
        if cur is None:
            continue
        prof = cur.profile_json or {}
        cols = []
        for c in prof.get("columns", []) or [
            {"name": s["name"], "type": s["type"], "kind": "?"} for s in cur.schema_json
        ]:
            entry: dict[str, Any] = {"name": c["name"], "type": c["type"], "kind": c.get("kind")}
            if c.get("is_date_candidate") and c.get("temporal"):
                entry["range"] = [c["temporal"]["min"], c["temporal"]["max"]]
            if c.get("is_dimension_candidate") and c.get("top_values"):
                entry["values"] = [str(v["value"]) for v in c["top_values"][:8]]
            if c.get("is_id_like"):
                entry["role"] = "identifier"
            elif c.get("kind") == "numeric" and c.get("distinct_count", 3) <= 2:
                entry["role"] = "binary_flag"
            cols.append(entry)
        out.append(
            {
                "table": ds.table_name,
                "name": ds.display_name,
                "rows": cur.row_count,
                "version_id": cur.id,
                "columns": cols,
                "date_columns": prof.get("candidate_date_columns", []),
                "dimensions": prof.get("candidate_dimensions", []),
                "measures": prof.get("candidate_measures", []),
            }
        )
    return out


def catalog_text(catalog: list[dict[str, Any]]) -> str:
    lines = []
    for t in catalog:
        lines.append(f"TABLE {t['table']} ({t['rows']} rows)")
        for c in t["columns"]:
            extra = []
            if "range" in c:
                extra.append(f"range {c['range'][0]} .. {c['range'][1]}")
            if "values" in c:
                extra.append("values: " + ", ".join(c["values"]))
            if "role" in c:
                extra.append(c["role"])
            suffix = f"  [{'; '.join(extra)}]" if extra else ""
            lines.append(f"  - {c['name']}: {c['type']}{suffix}")
    return "\n".join(lines)
