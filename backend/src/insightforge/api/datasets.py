from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from insightforge.api.deps import AppSettings, DatasetDep, DbSession
from insightforge.db.models import Dataset, DatasetVersion
from insightforge.engine.duck import locked_connection, quote_ident
from insightforge.ingest.formats import IngestError
from insightforge.ingest.service import (
    add_version,
    delete_dataset,
    ingest_file,
    safe_filename,
    spool_upload,
)
from insightforge.profiling.engine import profile_parquet

router = APIRouter(prefix="/datasets", tags=["datasets"])


class ColumnOut(BaseModel):
    name: str
    type: str
    nullable: bool


class VersionOut(BaseModel):
    id: str
    version: int
    source_format: str
    source_name: str
    sha256: str
    row_count: int
    column_count: int
    created_at: datetime


class DatasetOut(BaseModel):
    id: str
    table_name: str
    display_name: str
    description: str | None
    is_demo: bool
    created_at: datetime
    current: VersionOut
    columns: list[ColumnOut]
    version_count: int


class PreviewOut(BaseModel):
    columns: list[ColumnOut]
    rows: list[list[Any]]
    total_rows: int
    offset: int
    limit: int


def to_out(ds: Dataset) -> DatasetOut:
    cur = ds.current
    assert cur is not None
    return DatasetOut(
        id=ds.id,
        table_name=ds.table_name,
        display_name=ds.display_name,
        description=ds.description,
        is_demo=ds.is_demo,
        created_at=ds.created_at,
        current=VersionOut.model_validate(cur, from_attributes=True),
        columns=[ColumnOut(**c) for c in cur.schema_json],
        version_count=len(ds.versions),
    )


@router.get("", response_model=list[DatasetOut])
def list_datasets(db: DbSession) -> list[DatasetOut]:
    return [to_out(d) for d in db.scalars(select(Dataset).order_by(Dataset.created_at))]


@router.post("", response_model=list[DatasetOut], status_code=status.HTTP_201_CREATED)
def upload_dataset(
    db: DbSession,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form(max_length=120)] = None,
) -> list[DatasetOut]:
    try:
        filename = safe_filename(file.filename)
        path, sha, _ = spool_upload(file.file, settings, settings.max_upload_bytes)
        try:
            created = ingest_file(
                db, settings, upload_path=path, filename=filename, sha256=sha, display_name=name
            )
        finally:
            path.unlink(missing_ok=True)
    except IngestError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [to_out(d) for d in created]


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(ds: DatasetDep) -> DatasetOut:
    return to_out(ds)


@router.get("/{dataset_id}/versions", response_model=list[VersionOut])
def list_versions(ds: DatasetDep) -> list[VersionOut]:
    return [VersionOut.model_validate(v, from_attributes=True) for v in ds.versions]


@router.post("/{dataset_id}/versions", response_model=DatasetOut, status_code=201)
def upload_version(
    ds: DatasetDep, db: DbSession, settings: AppSettings, file: Annotated[UploadFile, File()]
) -> DatasetOut:
    try:
        filename = safe_filename(file.filename)
        path, sha, _ = spool_upload(file.file, settings, settings.max_upload_bytes)
        try:
            add_version(db, settings, ds, upload_path=path, filename=filename, sha256=sha)
        finally:
            path.unlink(missing_ok=True)
    except IngestError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_out(ds)


@router.delete("/{dataset_id}", status_code=204)
def remove_dataset(ds: DatasetDep, db: DbSession, settings: AppSettings) -> None:
    delete_dataset(db, settings, ds)


@router.get("/{dataset_id}/profile")
def get_profile(
    ds: DatasetDep, db: DbSession, settings: AppSettings, version: int | None = None
) -> dict[str, Any]:
    """Real per-column statistics, computed at ingest and cached on the version."""
    ver = _pick_version(ds, version)
    if ver.profile_json is None:
        ver.profile_json = profile_parquet(
            settings.datasets_dir / ver.storage_path, ver.schema_json
        )
        db.commit()
    return {"dataset_id": ds.id, "version": ver.version, **ver.profile_json}


@router.get("/{dataset_id}/preview", response_model=PreviewOut)
def preview(
    ds: DatasetDep,
    settings: AppSettings,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    sort: str | None = None,
    order: Literal["asc", "desc"] = "asc",
    search: Annotated[str | None, Query(max_length=200)] = None,
    version: int | None = None,
) -> PreviewOut:
    ver = _pick_version(ds, version)
    cols = [ColumnOut(**c) for c in ver.schema_json]
    names = {c.name for c in cols}
    if sort is not None and sort not in names:
        raise HTTPException(status_code=422, detail="Unknown sort column")

    q = quote_ident
    # Identifiers come only from the stored schema; user values are bound parameters.
    where, params = "", []
    if search:
        where = " WHERE " + " OR ".join(f"CAST({q(c.name)} AS VARCHAR) ILIKE ?" for c in cols)
        params = [f"%{search}%"] * len(cols)
    order_sql = f" ORDER BY {q(sort)} {order.upper()} NULLS LAST" if sort else ""
    con = locked_connection({"t": settings.datasets_dir / ver.storage_path})
    try:
        total = con.execute(f"SELECT count(*) FROM t{where}", params).fetchone()  # noqa: S608
        rows = con.execute(
            f"SELECT * FROM t{where}{order_sql} LIMIT ? OFFSET ?",  # noqa: S608
            [*params, limit, offset],
        ).fetchall()
    finally:
        con.close()
    return PreviewOut(
        columns=cols,
        rows=[list(r) for r in rows],
        total_rows=int(total[0]) if total else 0,
        offset=offset,
        limit=limit,
    )


def _pick_version(ds: Dataset, version: int | None) -> DatasetVersion:
    if version is None:
        assert ds.current is not None
        return ds.current
    for v in ds.versions:
        if v.version == version:
            return v
    raise HTTPException(status_code=404, detail="Version not found")
