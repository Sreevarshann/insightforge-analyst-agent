"""Typed argument and result models for analytical operations.

The agent (or a user) never supplies code: it selects an operation by name and fills a
schema-validated argument object. Column and table names are re-validated against the
live dataset schema before anything runs.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Ident = Annotated[str, Field(min_length=1, max_length=255)]
Agg = Literal["sum", "avg", "count", "count_distinct", "min", "max", "median"]
Grain = Literal["day", "week", "month", "quarter", "year"]


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: Ident
    op: Literal["=", "!=", ">", ">=", "<", "<=", "in", "not_in", "between", "is_null", "not_null"]
    value: Any = None

    @model_validator(mode="after")
    def _check_value(self) -> Filter:
        if self.op in {"is_null", "not_null"}:
            return self
        if self.op in {"in", "not_in"}:
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 200:
                raise ValueError("'in' filters need a list of 1-200 values")
        elif self.op == "between":
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("'between' needs [low, high]")
        elif self.value is None or isinstance(self.value, (dict, list)):
            raise ValueError("comparison filters need a scalar value")
        return self


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: Ident  # dataset table_name
    filters: list[Filter] = Field(default_factory=list, max_length=20)


class DescribeArgs(_Op):
    op: Literal["describe"] = "describe"
    columns: list[Ident] = Field(default_factory=list, max_length=50)


class AggregateArgs(_Op):
    op: Literal["aggregate"] = "aggregate"
    measure: Ident | None = None  # None only valid with agg="count"
    agg: Agg = "sum"
    group_by: list[Ident] = Field(default_factory=list, max_length=3)
    date_column: Ident | None = None
    time_grain: Grain | None = None
    sort: Literal["value_desc", "value_asc", "group"] = "value_desc"
    limit: int = Field(default=50, ge=1, le=1000)

    @model_validator(mode="after")
    def _check(self) -> AggregateArgs:
        if self.measure is None and self.agg != "count":
            raise ValueError("measure is required unless agg is 'count'")
        if (self.time_grain is None) != (self.date_column is None):
            raise ValueError("date_column and time_grain must be given together")
        return self


class TrendArgs(_Op):
    op: Literal["trend"] = "trend"
    measure: Ident | None = None
    agg: Agg = "sum"
    date_column: Ident
    grain: Grain = "month"
    group_by: Ident | None = None
    start: dt.date | None = None
    end: dt.date | None = None


class GroupCompareArgs(_Op):
    op: Literal["group_compare"] = "group_compare"
    measure: Ident
    group_column: Ident
    groups: list[str] = Field(default_factory=list, max_length=20)


class RateArgs(_Op):
    """Share of rows where a boolean/0-1 outcome is true, per group (e.g. churn rate)."""

    op: Literal["rate"] = "rate"
    outcome: Ident
    group_by: list[Ident] = Field(default_factory=list, max_length=2)
    min_group_size: int = Field(default=1, ge=1)


class CorrelationArgs(_Op):
    op: Literal["correlation"] = "correlation"
    columns: list[Ident] = Field(min_length=2, max_length=12)
    method: Literal["pearson", "spearman"] = "pearson"


class CohortArgs(_Op):
    op: Literal["cohort_retention"] = "cohort_retention"
    entity_column: Ident
    date_column: Ident
    grain: Literal["week", "month", "quarter"] = "month"
    max_periods: int = Field(default=12, ge=1, le=36)
    cohorts: list[str] = Field(default_factory=list, max_length=24)


class SegmentArgs(_Op):
    op: Literal["segment"] = "segment"
    features: list[Ident] = Field(min_length=1, max_length=10)
    k: int = Field(default=4, ge=2, le=10)
    entity_column: Ident | None = None


class OutlierArgs(_Op):
    op: Literal["outliers"] = "outliers"
    column: Ident
    method: Literal["iqr", "zscore"] = "iqr"
    threshold: float = Field(default=1.5, gt=0, le=10)
    group_by: Ident | None = None
    min_group_size: int = Field(default=5, ge=1)


class RegressionArgs(_Op):
    op: Literal["regression"] = "regression"
    target: Ident
    features: list[Ident] = Field(min_length=1, max_length=10)


class ForecastArgs(_Op):
    op: Literal["forecast"] = "forecast"
    measure: Ident | None = None
    agg: Agg = "sum"
    date_column: Ident
    grain: Literal["day", "week", "month", "quarter"] = "month"
    horizon: int = Field(default=6, ge=1, le=36)


class MissingArgs(_Op):
    op: Literal["missing_values"] = "missing_values"


OpArgs = Annotated[
    DescribeArgs
    | AggregateArgs
    | TrendArgs
    | GroupCompareArgs
    | RateArgs
    | CorrelationArgs
    | CohortArgs
    | SegmentArgs
    | OutlierArgs
    | RegressionArgs
    | ForecastArgs
    | MissingArgs,
    Field(discriminator="op"),
]


class Fact(BaseModel):
    """A single computed number the explanation is allowed to cite."""

    id: str
    label: str
    value: float | int | str | None
    unit: Literal["count", "currency", "percent", "ratio", "number", "date", "pvalue", "text"]
    source: dict[str, Any] = Field(default_factory=dict)


class ResultTable(BaseModel):
    name: str
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool = False


class OpResult(BaseModel):
    op: str
    args: dict[str, Any]
    tables: list[ResultTable]
    facts: list[Fact]
    notes: list[str] = Field(default_factory=list)
    query_ids: list[str] = Field(default_factory=list)
    sql: list[str] = Field(default_factory=list)
    dataset_versions: list[str] = Field(default_factory=list)
    chart_hint: dict[str, Any] | None = None
