from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from insightforge.config import Settings
from insightforge.db.models import Dataset
from insightforge.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


AppSettings = Annotated[Settings, Depends(get_app_settings)]


def load_dataset(dataset_id: str, db: DbSession) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


DatasetDep = Annotated[Dataset, Depends(load_dataset)]
