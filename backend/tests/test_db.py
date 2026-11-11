from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from insightforge.db.models import Analysis, Dataset, DatasetVersion
from insightforge.db.session import make_engine, make_sessionmaker, run_migrations


@pytest.fixture
def session(tmp_path: Path) -> Session:
    engine = make_engine(tmp_path / "meta.sqlite3")
    run_migrations(engine)
    return make_sessionmaker(engine)()


def _version(n: int) -> DatasetVersion:
    return DatasetVersion(
        version=n,
        source_format="csv",
        source_name="orders.csv",
        sha256="0" * 64,
        storage_path=f"x/v{n}.parquet",
        row_count=10,
        column_count=3,
        schema_json=[{"name": "a", "type": "BIGINT"}],
    )


def test_migrations_create_all_tables(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "m.sqlite3")
    run_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"datasets", "dataset_versions", "relationships", "analyses", "query_log"} <= tables
    run_migrations(engine)  # idempotent


def test_dataset_versions_are_ordered_and_current(session: Session) -> None:
    ds = Dataset(table_name="orders", display_name="Orders")
    ds.versions.extend([_version(1), _version(2)])
    session.add(ds)
    session.commit()
    loaded = session.scalars(select(Dataset)).one()
    assert loaded.current is not None and loaded.current.version == 2


def test_table_name_is_unique(session: Session) -> None:
    session.add_all(
        [Dataset(table_name="t", display_name="A"), Dataset(table_name="t", display_name="B")]
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_dataset_cascades_to_versions(session: Session) -> None:
    ds = Dataset(table_name="c", display_name="C")
    ds.versions.append(_version(1))
    session.add(ds)
    session.commit()
    session.delete(ds)
    session.commit()
    assert session.scalars(select(DatasetVersion)).all() == []


def test_analysis_json_roundtrip(session: Session) -> None:
    a = Analysis(question="q?", plan_json={"steps": [1, 2]}, steps_json=[{"tool": "sql"}])
    session.add(a)
    session.commit()
    session.expire_all()
    got = session.get(Analysis, a.id)
    assert got is not None and got.plan_json == {"steps": [1, 2]} and got.status == "pending"
