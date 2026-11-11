from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from insightforge.api.deps import AppSettings, DbSession
from insightforge.db.models import Dataset, Relationship
from insightforge.relationships import RelationshipError, create_relationship

router = APIRouter(prefix="/relationships", tags=["relationships"])


class RelationshipIn(BaseModel):
    left_dataset_id: str
    left_column: str
    right_dataset_id: str
    right_column: str


class RelationshipOut(RelationshipIn):
    id: str
    cardinality: str
    created_at: datetime


@router.get("", response_model=list[RelationshipOut])
def list_relationships(db: DbSession) -> list[RelationshipOut]:
    return [
        RelationshipOut.model_validate(r, from_attributes=True)
        for r in db.scalars(select(Relationship))
    ]


@router.post("", response_model=RelationshipOut, status_code=201)
def create(body: RelationshipIn, db: DbSession, settings: AppSettings) -> RelationshipOut:
    left, right = db.get(Dataset, body.left_dataset_id), db.get(Dataset, body.right_dataset_id)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        rel = create_relationship(db, settings, left, body.left_column, right, body.right_column)
    except RelationshipError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RelationshipOut.model_validate(rel, from_attributes=True)


@router.delete("/{relationship_id}", status_code=204)
def delete(relationship_id: str, db: DbSession) -> None:
    rel = db.get(Relationship, relationship_id)
    if rel is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    db.delete(rel)
    db.commit()
