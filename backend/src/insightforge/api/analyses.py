from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from insightforge.agent.service import run_analysis
from insightforge.api.deps import AppSettings, DbSession
from insightforge.charts.builder import ChartConfig, ChartError, build_figure
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


def _load(analysis_id: str, db: DbSession) -> Analysis:
    a = db.get(Analysis, analysis_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return a


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


@router.post("/stream", response_class=EventSourceResponse)
def create_stream(
    body: AnalysisIn, request: Request, settings: AppSettings
) -> Iterator[dict[str, Any]]:
    """Run an analysis and stream the agent's real progress events as SSE.

    The graph runs in a worker thread with its own DB session; events are forwarded as
    they are emitted by graph nodes (stage start/finish, plan, results, charts,
    verified explanation), followed by the persisted analysis.
    """
    provider = get_provider(request, settings)
    factory = request.app.state.sessionmaker
    explain_factory = request.app.state.explain_factory
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def work() -> None:
        with factory() as db:
            try:
                a = run_analysis(
                    db,
                    settings,
                    provider,
                    body.question,
                    dataset_ids=body.dataset_ids,
                    on_event=events.put,
                    explain_factory=explain_factory,
                )
                events.put({"type": "done", "analysis": to_out(a).model_dump(mode="json")})
            except Exception:
                events.put({"type": "error", "message": "The analysis failed unexpectedly."})
            finally:
                events.put(None)

    threading.Thread(target=work, daemon=True, name="analysis-stream").start()
    while (event := events.get()) is not None:
        yield event


class AnalysisPatch(BaseModel):
    saved: bool | None = None
    title: str | None = Field(default=None, max_length=255)


@router.patch("/{analysis_id}", response_model=AnalysisOut)
def update(analysis_id: str, body: AnalysisPatch, db: DbSession) -> AnalysisOut:
    a = _load(analysis_id, db)
    if body.saved is not None:
        a.saved = body.saved
    if body.title is not None:
        a.title = body.title
    db.commit()
    return to_out(a)


@router.get("", response_model=list[AnalysisOut])
def list_analyses(
    db: DbSession, saved: bool | None = None, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[AnalysisOut]:
    stmt = select(Analysis).order_by(Analysis.created_at.desc()).limit(limit)
    if saved is not None:
        stmt = stmt.where(Analysis.saved == saved)
    return [to_out(a) for a in db.scalars(stmt)]


class ChartIn(BaseModel):
    step: int = Field(ge=1)
    config: ChartConfig


@router.post("/{analysis_id}/charts/preview")
def preview_chart(analysis_id: str, body: ChartIn, db: DbSession) -> dict[str, Any]:
    """Chart Studio: rebuild a figure from the stored result tables with a user config."""
    a = _load(analysis_id, db)
    step = next((s for s in a.steps_json if s.get("step") == body.step), None)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    try:
        return {"step": body.step, **build_figure(body.config, step["tables"])}
    except ChartError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/{analysis_id}/charts", response_model=AnalysisOut)
def save_charts(analysis_id: str, body: list[ChartIn], db: DbSession) -> AnalysisOut:
    """Persist the chart views shown for an analysis (rebuilt server-side, never stored raw)."""
    a = _load(analysis_id, db)
    charts = []
    for c in body:
        step = next((s for s in a.steps_json if s.get("step") == c.step), None)
        if step is None:
            raise HTTPException(status_code=404, detail=f"Step {c.step} not found")
        try:
            charts.append({"step": c.step, **build_figure(c.config, step["tables"])})
        except ChartError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    a.charts_json = charts
    db.commit()
    return to_out(a)


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get(analysis_id: str, db: DbSession) -> AnalysisOut:
    a = db.get(Analysis, analysis_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return to_out(a)
