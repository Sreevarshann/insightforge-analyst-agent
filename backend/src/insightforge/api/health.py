from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from insightforge import __version__
from insightforge.config import Settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    llm_provider: str


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment,
        llm_provider=settings.llm_provider,
    )
