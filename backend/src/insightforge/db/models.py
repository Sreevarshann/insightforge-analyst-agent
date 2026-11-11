"""Metadata models. Analytical data itself lives in Parquet files queried by DuckDB."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[Any]: JSON}


class Dataset(Base):
    """A logical dataset. Each re-upload creates a new immutable DatasetVersion."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    # SQL-safe identifier used as the table/view name inside analytical queries.
    table_name: Mapped[str] = mapped_column(String(63), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_demo: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    versions: Mapped[list[DatasetVersion]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetVersion.version",
    )

    @property
    def current(self) -> DatasetVersion | None:
        return self.versions[-1] if self.versions else None


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    source_format: Mapped[str] = mapped_column(String(16))  # csv, tsv, xlsx, parquet, sqlite, pg
    source_name: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    # Path of the canonical Parquet file, relative to settings.datasets_dir.
    storage_path: Mapped[str] = mapped_column(String(512))
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    schema_json: Mapped[list[Any]] = mapped_column(default=list)
    profile_json: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    dataset: Mapped[Dataset] = relationship(back_populates="versions")


class Relationship(Base):
    """An explicit, validated join path between two datasets."""

    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("left_dataset_id", "left_column", "right_dataset_id", "right_column"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    left_dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    left_column: Mapped[str] = mapped_column(String(255))
    right_dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    right_column: Mapped[str] = mapped_column(String(255))
    cardinality: Mapped[str] = mapped_column(String(16))  # one_to_one, many_to_one, ...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Analysis(Base):
    """A saved, reproducible analysis: question, plan, executed steps, results, explanation."""

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    title: Mapped[str | None] = mapped_column(String(255), default=None)
    # Dataset version ids the analysis ran against (pins reproducibility).
    dataset_versions: Mapped[list[Any]] = mapped_column(default=list)
    plan_json: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    steps_json: Mapped[list[Any]] = mapped_column(default=list)
    charts_json: Mapped[list[Any]] = mapped_column(default=list)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    verification_json: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    model_name: Mapped[str | None] = mapped_column(String(128), default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    saved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class QueryLog(Base):
    """Every SQL statement submitted for execution, accepted or rejected."""

    __tablename__ = "query_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("analyses.id", ondelete="SET NULL"), default=None
    )
    sql: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(16))  # agent | user
    accepted: Mapped[bool] = mapped_column()
    rejection_reason: Mapped[str | None] = mapped_column(Text, default=None)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
