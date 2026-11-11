"""Execution context shared by operations: schema lookup, safe SQL building, audited fetch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlglot import exp

from insightforge.config import Settings
from insightforge.db.models import Dataset
from insightforge.engine.duck import quote_ident
from insightforge.ops.models import Filter, Grain
from insightforge.profiling.engine import kind_of
from insightforge.sql.service import execute_query


class OpError(ValueError):
    """Invalid arguments for the selected data (user/agent fixable)."""


def lit(value: Any) -> str:
    """Render a Python scalar as a DuckDB literal via SQLGlot (never string concatenation)."""
    return exp.convert(value).sql(dialect="duckdb")


@dataclass
class OpContext:
    db: Session
    settings: Settings
    analysis_id: str | None = None
    query_ids: list[str] = field(default_factory=list)
    sql: list[str] = field(default_factory=list)
    dataset_versions: list[str] = field(default_factory=list)

    def schema(self, table: str) -> dict[str, str]:
        ds = self.db.scalars(select(Dataset).where(Dataset.table_name == table)).first()
        if ds is None or ds.current is None:
            raise OpError(f"Unknown dataset '{table}'")
        return {c["name"]: c["type"] for c in ds.current.schema_json}

    def column(self, table: str, name: str, *, kinds: set[str] | None = None) -> str:
        schema = self.schema(table)
        match = next((c for c in schema if c == name), None) or next(
            (c for c in schema if c.lower() == name.lower()), None
        )
        if match is None:
            raise OpError(f"Column '{name}' does not exist in '{table}'")
        if (
            kinds
            and kind_of(schema[match]) not in kinds
            and not ("temporal" in kinds and kind_of(schema[match]) == "text")
        ):
            raise OpError(f"Column '{match}' has type {schema[match]}, expected {sorted(kinds)}")
        return match

    def q(self, table: str, name: str, **kw: Any) -> str:
        return quote_ident(self.column(table, name, **kw))

    def where(self, table: str, filters: list[Filter]) -> str:
        parts = []
        for f in filters:
            c = self.q(table, f.column)
            match f.op:
                case "is_null":
                    parts.append(f"{c} IS NULL")
                case "not_null":
                    parts.append(f"{c} IS NOT NULL")
                case "in" | "not_in":
                    vals = ", ".join(lit(v) for v in f.value)
                    parts.append(f"{c} {'NOT IN' if f.op == 'not_in' else 'IN'} ({vals})")
                case "between":
                    parts.append(f"{c} BETWEEN {lit(f.value[0])} AND {lit(f.value[1])}")
                case _:
                    parts.append(f"{c} {f.op} {lit(f.value)}")
        return (" WHERE " + " AND ".join(parts)) if parts else ""

    def bucket(self, table: str, date_column: str, grain: Grain) -> str:
        c = self.q(table, date_column, kinds={"temporal"})
        return f"CAST(date_trunc({lit(grain)}, CAST({c} AS DATE)) AS DATE)"

    def fetch(
        self, sql: str, *, max_rows: int | None = None
    ) -> tuple[list[str], list[list[Any]], bool]:
        res = execute_query(
            self.db,
            self.settings,
            sql,
            origin="agent",
            analysis_id=self.analysis_id,
            max_rows=max_rows,
            hard_cap=self.settings.analysis_max_rows,
        )
        self.query_ids.append(res.query_id)
        self.sql.append(res.sql)
        for v in res.dataset_versions:
            if v not in self.dataset_versions:
                self.dataset_versions.append(v)
        return res.columns, res.rows, res.truncated

    def frame(self, sql: str) -> Any:
        import pandas as pd

        cols, rows, truncated = self.fetch(sql, max_rows=self.settings.analysis_max_rows)
        if truncated:
            raise OpError(
                f"Operation needs more than {self.settings.analysis_max_rows} rows; add filters"
            )
        return pd.DataFrame(rows, columns=cols)
