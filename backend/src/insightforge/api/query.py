from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from insightforge.api.deps import AppSettings, DbSession
from insightforge.db.models import QueryLog
from insightforge.sql.service import QueryFailed, execute_query
from insightforge.sql.validator import SQLRejected

router = APIRouter(prefix="/query", tags=["query"])


class QueryIn(BaseModel):
    sql: str = Field(min_length=1, max_length=20_000)
    max_rows: int | None = Field(default=None, ge=1, le=10_000)


class QueryOut(BaseModel):
    query_id: str
    sql: str
    columns: list[str]
    types: list[str]
    rows: list[list[Any]]
    truncated: bool
    elapsed_ms: float
    isolation: str
    tables: list[str]
    dataset_versions: list[str]


class QueryLogOut(BaseModel):
    id: str
    sql: str
    origin: str
    accepted: bool
    rejection_reason: str | None
    row_count: int | None
    duration_ms: int | None
    analysis_id: str | None
    created_at: datetime


@router.post("", response_model=QueryOut)
def run_query(body: QueryIn, db: DbSession, settings: AppSettings) -> QueryOut:
    try:
        result = execute_query(db, settings, body.sql, origin="user", max_rows=body.max_rows)
    except SQLRejected as exc:
        raise HTTPException(
            status_code=422, detail={"kind": "rejected", "message": str(exc)}
        ) from exc
    except QueryFailed as exc:
        raise HTTPException(
            status_code=400, detail={"kind": "execution", "message": str(exc)}
        ) from exc
    return QueryOut(**asdict(result))


@router.get("/history", response_model=list[QueryLogOut])
def history(db: DbSession, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[QueryLogOut]:
    rows = db.scalars(select(QueryLog).order_by(QueryLog.created_at.desc()).limit(limit))
    return [QueryLogOut.model_validate(r, from_attributes=True) for r in rows]
