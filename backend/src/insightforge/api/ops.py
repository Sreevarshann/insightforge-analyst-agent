from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import TypeAdapter, ValidationError

from insightforge.api.deps import AppSettings, DbSession
from insightforge.ops.context import OpContext, OpError
from insightforge.ops.models import OpArgs, OpResult
from insightforge.ops.operations import REGISTRY, run_operation
from insightforge.sql.service import QueryFailed
from insightforge.sql.validator import SQLRejected

router = APIRouter(prefix="/ops", tags=["operations"])
_adapter: TypeAdapter[Any] = TypeAdapter(OpArgs)


@router.get("")
def list_operations() -> dict[str, Any]:
    """Operation names and their JSON schemas (used by the agent planner and the UI)."""
    return {"operations": sorted(REGISTRY), "schema": _adapter.json_schema()}


@router.post("/run", response_model=OpResult)
def run(body: dict[str, Any], db: DbSession, settings: AppSettings) -> OpResult:
    try:
        args = _adapter.validate_python(body)
    except ValidationError as exc:
        errors = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
        raise HTTPException(status_code=422, detail=errors) from exc
    try:
        return run_operation(OpContext(db=db, settings=settings), args)
    except (OpError, SQLRejected) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except QueryFailed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
