"""Turn a raw SQL result into an OpResult with citable facts."""

from __future__ import annotations

from insightforge.ops.models import Fact, OpResult, ResultTable
from insightforge.sql.service import QueryResult

NUMERIC_PREFIX = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "DOUBLE",
    "FLOAT",
    "DECIMAL",
    "UBIGINT",
    "UINTEGER",
)


def sql_to_result(res: QueryResult, purpose: str) -> OpResult:
    numeric = [i for i, t in enumerate(res.types) if t.upper().startswith(NUMERIC_PREFIX)]
    labels = [i for i in range(len(res.columns)) if i not in numeric]
    facts: list[Fact] = []
    for r in res.rows[:60]:
        key = ", ".join(f"{res.columns[i]}={r[i]}" for i in labels)
        for i in numeric:
            label = f"{res.columns[i]}" + (f" for {key}" if key else "")
            facts.append(
                Fact(
                    id=f"q{len(facts) + 1}",
                    label=label,
                    value=r[i],
                    unit="number",
                    source={"column": res.columns[i], "row": key},
                )
            )
    hint = None
    if labels and numeric:
        hint = {
            "type": "bar",
            "x": res.columns[labels[0]],
            "y": res.columns[numeric[0]],
            "table": "result",
        }
    return OpResult(
        op="sql",
        args={"sql": res.sql, "purpose": purpose},
        tables=[
            ResultTable(name="result", columns=res.columns, rows=res.rows, truncated=res.truncated)
        ],
        facts=facts,
        query_ids=[res.query_id],
        sql=[res.sql],
        dataset_versions=res.dataset_versions,
        chart_hint=hint,
        notes=["Result truncated at the row limit."] if res.truncated else [],
    )
