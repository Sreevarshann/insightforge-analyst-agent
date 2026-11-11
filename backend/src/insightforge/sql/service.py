"""Validated, sandboxed, audited SQL execution against registered datasets."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from insightforge.config import Settings
from insightforge.db.models import Dataset, QueryLog, Relationship
from insightforge.sql.sandbox import SandboxLimits, run_sandboxed
from insightforge.sql.validator import SQLRejected, validate_sql


@dataclass
class QueryResult:
    query_id: str
    sql: str
    columns: list[str]
    types: list[str]
    rows: list[list[Any]]
    truncated: bool
    elapsed_ms: float
    isolation: str
    tables: list[str] = field(default_factory=list)
    dataset_versions: list[str] = field(default_factory=list)


class QueryFailed(RuntimeError):
    def __init__(self, message: str, query_id: str) -> None:
        super().__init__(message)
        self.query_id = query_id


def dataset_catalog(db: Session, settings: Settings) -> dict[str, tuple[Path, str]]:
    """table_name -> (parquet path of current version, version id)."""
    out: dict[str, tuple[Path, str]] = {}
    for ds in db.scalars(select(Dataset)):
        cur = ds.current
        if cur is not None:
            out[ds.table_name] = (settings.datasets_dir / cur.storage_path, cur.id)
    return out


def relationship_keys(db: Session) -> list[tuple[str, str, str, str]]:
    names = {d.id: d.table_name.lower() for d in db.scalars(select(Dataset))}
    return [
        (
            names[r.left_dataset_id],
            r.left_column.lower(),
            names[r.right_dataset_id],
            r.right_column.lower(),
        )
        for r in db.scalars(select(Relationship))
        if r.left_dataset_id in names and r.right_dataset_id in names
    ]


def execute_query(
    db: Session,
    settings: Settings,
    sql: str,
    *,
    origin: Literal["agent", "user"],
    analysis_id: str | None = None,
    max_rows: int | None = None,
    hard_cap: int | None = None,
) -> QueryResult:
    catalog = dataset_catalog(db, settings)
    log = QueryLog(sql=sql[:20_000], origin=origin, analysis_id=analysis_id, accepted=False)
    db.add(log)
    try:
        validated = validate_sql(sql, catalog.keys(), relationship_keys(db))
    except SQLRejected as exc:
        log.rejection_reason = str(exc)
        db.commit()
        raise
    log.accepted = True
    limits = SandboxLimits(
        timeout_seconds=settings.query_timeout_seconds,
        memory_mb=settings.sandbox_memory_mb,
        max_rows=min(max_rows or settings.query_max_rows, hard_cap or settings.query_max_rows),
    )
    views = {t: catalog[t][0] for t in sorted(validated.tables)}
    started = time.perf_counter()
    result = run_sandboxed(validated.sql, views, limits)
    log.duration_ms = int((time.perf_counter() - started) * 1000)
    if not result.ok:
        log.rejection_reason = f"execution: {result.error}"
        db.commit()
        raise QueryFailed(result.error or "Query failed", log.id)
    log.row_count = len(result.rows)
    db.commit()
    return QueryResult(
        query_id=log.id,
        sql=validated.sql,
        columns=result.columns,
        types=result.types,
        rows=result.rows,
        truncated=result.truncated,
        elapsed_ms=result.elapsed_ms,
        isolation=result.isolation,
        tables=sorted(validated.tables),
        dataset_versions=[catalog[t][1] for t in sorted(validated.tables)],
    )
