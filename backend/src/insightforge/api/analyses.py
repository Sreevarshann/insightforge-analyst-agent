from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from insightforge.agent.service import run_analysis
from insightforge.api.deps import AppSettings, DbSession
from insightforge.db.models import Analysis
from insightforge.llm.base import LLMProvider
from insightforge.llm.factory import make_provider

router = APIRouter(prefix="/analyses", tags=["analyses"])


class AnalysisIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    dataset_ids: list[str] = Field(default_factory=list, max_length=20)


class AnalysisOut(BaseModel):
    id: str
    question: str
    status: str
    title: str | None
    explanation: str | None
    plan: dict[str, Any] | None
    steps: list[Any]
    charts: list[Any]
    verification: dict[str, Any] | None
    dataset_versions: list[Any]
    model_name: str | None
    duration_ms: int | None
    saved: bool
    created_at: datetime


def to_out(a: Analysis) -> AnalysisOut:
    return AnalysisOut(
        id=a.id, question=a.question, status=a.status, title=a.title, explanation=a.explanation,
        plan=a.plan_json, steps=a.steps_json, charts=a.charts_json, verification=a.verification_json,
        dataset_versions=a.dataset_versions, model_name=a.model_name, duration_ms=a.duration_ms,
        saved=a.saved, created_at=a.created_at,
    )  # fmt: skip


def get_provider(request: Request, settings: AppSettings) -> LLMProvider:
    factory = getattr(request.app.state, "provider_factory", None)
    return factory() if factory else make_provider(settings)


@router.post("", response_model=AnalysisOut, status_code=201)
def create(body: AnalysisIn, request: Request, db: DbSession, settings: AppSettings) -> AnalysisOut:
    provider = get_provider(request, settings)
    return to_out(
        run_analysis(
            db,
            settings,
            provider,
            body.question,
            dataset_ids=body.dataset_ids,
            explain_factory=request.app.state.explain_factory,
        )
    )


@router.get("", response_model=list[AnalysisOut])
def list_analyses(
    db: DbSession, saved: bool | None = None, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[AnalysisOut]:
    stmt = select(Analysis).order_by(Analysis.created_at.desc()).limit(limit)
    if saved is not None:
        stmt = stmt.where(Analysis.saved == saved)
    return [to_out(a) for a in db.scalars(stmt)]


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get(analysis_id: str, db: DbSession) -> AnalysisOut:
    a = db.get(Analysis, analysis_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return to_out(a)
