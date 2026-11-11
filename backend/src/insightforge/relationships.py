"""Explicit, data-validated join relationships between datasets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from insightforge.config import Settings
from insightforge.db.models import Dataset, Relationship
from insightforge.engine.duck import locked_connection, quote_ident


class RelationshipError(ValueError):
    pass


def _column(ds: Dataset, name: str) -> dict[str, str]:
    assert ds.current is not None
    col: dict[str, str] | None = next(
        (c for c in ds.current.schema_json if c["name"] == name), None
    )
    if col is None:
        raise RelationshipError(f"Column '{name}' does not exist in '{ds.table_name}'")
    return col


def create_relationship(
    db: Session,
    settings: Settings,
    left: Dataset,
    left_col: str,
    right: Dataset,
    right_col: str,
    *,
    exist_ok: bool = False,
) -> Relationship:
    """Validate type compatibility and key coverage on the data, infer cardinality, store."""
    existing = db.scalars(
        select(Relationship).where(
            Relationship.left_dataset_id == left.id,
            Relationship.left_column == left_col,
            Relationship.right_dataset_id == right.id,
            Relationship.right_column == right_col,
        )
    ).first()
    if existing:
        if exist_ok:
            return existing
        raise RelationshipError("Relationship already exists")
    lt, rt = _column(left, left_col)["type"], _column(right, right_col)["type"]
    numeric = ("INT", "BIGINT", "DOUBLE", "DECIMAL", "HUGEINT", "SMALLINT", "TINYINT", "FLOAT")
    if lt != rt and not (lt.startswith(numeric) and rt.startswith(numeric)):
        raise RelationshipError(f"Incompatible key types {lt} and {rt}")
    assert left.current and right.current
    con = locked_connection(
        {
            "l": settings.datasets_dir / left.current.storage_path,
            "r": settings.datasets_dir / right.current.storage_path,
        }
    )
    try:
        lq, rq = quote_ident(left_col), quote_ident(right_col)
        row = con.execute(
            f"SELECT (SELECT count(*) FROM l WHERE {lq} IS NOT NULL), "  # noqa: S608
            f"(SELECT count(*) FROM l WHERE {lq} IS NOT NULL AND {lq} IN (SELECT {rq} FROM r)), "
            f"(SELECT count(*) = count(DISTINCT {lq}) FROM l), (SELECT count(*) = count(DISTINCT {rq}) FROM r)"
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    non_null, matched, left_unique, right_unique = row
    if non_null == 0 or matched / non_null < 0.9:
        raise RelationshipError(
            f"Only {matched} of {non_null} keys in '{left.table_name}.{left_col}' match '{right.table_name}.{right_col}'"
        )
    cardinality = {
        (True, True): "one_to_one",
        (False, True): "many_to_one",
        (True, False): "one_to_many",
    }.get((bool(left_unique), bool(right_unique)), "many_to_many")
    rel = Relationship(
        left_dataset_id=left.id,
        left_column=left_col,
        right_dataset_id=right.id,
        right_column=right_col,
        cardinality=cardinality,
    )
    db.add(rel)
    db.commit()
    return rel
