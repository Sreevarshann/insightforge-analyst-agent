"""Analytical operations. Each one validates its columns against the live schema, computes
with DuckDB (via the sandboxed, audited query path) and/or vetted SciPy/scikit-learn/
statsmodels code, and returns tables plus *facts*: the only numbers an explanation may cite.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np

from insightforge.engine.duck import quote_ident
from insightforge.ops.context import OpContext, OpError, lit
from insightforge.ops.models import (
    AggregateArgs,
    CohortArgs,
    CorrelationArgs,
    DescribeArgs,
    Fact,
    ForecastArgs,
    GroupCompareArgs,
    MissingArgs,
    OpResult,
    OutlierArgs,
    RateArgs,
    RegressionArgs,
    ResultTable,
    SegmentArgs,
    TrendArgs,
)
from insightforge.profiling.engine import kind_of

NUMERIC = {"numeric"}
CAUSATION_NOTE = "This shows statistical association only; it does not establish causation."
MAX_FACT_ROWS = 60


class Facts:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.items: list[Fact] = []

    def add(self, label: str, value: Any, unit: str, **source: Any) -> str:
        fid = f"{self.prefix}{len(self.items) + 1}"
        v = _clean(value)
        self.items.append(
            Fact.model_validate(
                {"id": fid, "label": label, "value": v, "unit": unit, "source": source}
            )
        )
        return fid


def _clean(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    return v


def _agg_sql(agg: str, col: str | None) -> str:
    if agg == "count":
        return "count(*)" if col is None else f"count({col})"
    if agg == "count_distinct":
        return f"count(DISTINCT {col})"
    fn = {"avg": "avg", "sum": "sum", "min": "min", "max": "max", "median": "median"}[agg]
    return f"{fn}({col})"


def _unit_for(agg: str, measure: str | None) -> str:
    if agg in {"count", "count_distinct"}:
        return "count"
    name = (measure or "").lower()
    if any(
        k in name
        for k in (
            "revenue",
            "amount",
            "price",
            "cost",
            "mrr",
            "arr",
            "sales",
            "refund",
            "discount_value",
            "value_usd",
        )
    ):
        return "currency"
    return "number"


def _measure_label(agg: str, measure: str | None) -> str:
    return "row count" if measure is None else f"{agg}({measure})"


def _result(
    ctx: OpContext, op: str, args: Any, tables: list[ResultTable], facts: Facts, **kw: Any
) -> OpResult:
    return OpResult(
        op=op,
        args=args.model_dump(mode="json"),
        tables=tables,
        facts=facts.items,
        query_ids=list(ctx.query_ids),
        sql=list(ctx.sql),
        dataset_versions=list(ctx.dataset_versions),
        **kw,
    )


# ---------------------------------------------------------------- describe / missing


def describe(ctx: OpContext, a: DescribeArgs) -> OpResult:
    schema = ctx.schema(a.dataset)
    cols = [ctx.column(a.dataset, c) for c in a.columns] if a.columns else list(schema)
    t, where = quote_ident(a.dataset), ctx.where(a.dataset, a.filters)
    facts = Facts("d")
    rows = []
    for c in cols:
        q, kind = quote_ident(c), kind_of(schema[c])
        if kind == "numeric":
            sql = (
                f"SELECT count({q}), count(*) - count({q}), avg({q}), stddev_samp({q}), min({q}), "
                f"quantile_cont({q}, 0.25), median({q}), quantile_cont({q}, 0.75), max({q}), "
                f"count(DISTINCT {q}) FROM {t}{where}"
            )
        else:
            sql = (
                f"SELECT count({q}), count(*) - count({q}), NULL, NULL, CAST(min({q}) AS VARCHAR), NULL, "
                f"NULL, NULL, CAST(max({q}) AS VARCHAR), count(DISTINCT {q}) FROM {t}{where}"
            )
        _, r, _ = ctx.fetch(sql)
        vals = [_clean(v) for v in r[0]]
        rows.append([c, schema[c], *vals])
        facts.add(f"non-null count of {c}", vals[0], "count", column=c)
        facts.add(f"missing count of {c}", vals[1], "count", column=c)
        if kind == "numeric":
            for label, v in zip(
                ("mean", "std", "min", "p25", "median", "p75", "max"), vals[2:9], strict=True
            ):
                facts.add(f"{label} of {c}", v, _unit_for("sum", c), column=c, stat=label)
        facts.add(f"distinct values of {c}", vals[9], "count", column=c)
    header = [
        "column",
        "type",
        "count",
        "missing",
        "mean",
        "std",
        "min",
        "p25",
        "median",
        "p75",
        "max",
        "distinct",
    ]
    return _result(
        ctx, "describe", a, [ResultTable(name="summary", columns=header, rows=rows)], facts
    )


def missing_values(ctx: OpContext, a: MissingArgs) -> OpResult:
    schema = ctx.schema(a.dataset)
    t, where = quote_ident(a.dataset), ctx.where(a.dataset, a.filters)
    parts = ", ".join(f"count(*) - count({quote_ident(c)})" for c in schema)
    any_null = " OR ".join(f"{quote_ident(c)} IS NULL" for c in schema)
    _, r, _ = ctx.fetch(
        f"SELECT count(*), {parts}, count(*) FILTER (WHERE {any_null}) FROM {t}{where}"
    )
    total, *missing, rows_any = r[0]
    facts = Facts("m")
    facts.add("rows analysed", total, "count")
    facts.add("rows with any missing value", rows_any, "count")
    facts.add(
        "share of rows with any missing value",
        100.0 * rows_any / total if total else 0.0,
        "percent",
    )
    out = []
    for c, m in sorted(zip(schema, missing, strict=True), key=lambda x: -x[1]):
        pct = 100.0 * m / total if total else 0.0
        out.append([c, m, round(pct, 4)])
        if m:
            facts.add(f"missing values in {c}", m, "count", column=c)
            facts.add(f"missing share of {c}", pct, "percent", column=c)
    return _result(
        ctx,
        "missing_values",
        a,
        [ResultTable(name="missing", columns=["column", "missing", "missing_pct"], rows=out)],
        facts,
        chart_hint={"type": "bar", "x": "column", "y": "missing_pct", "table": "missing"},
    )


# ---------------------------------------------------------------- aggregate / trend


def aggregate(ctx: OpContext, a: AggregateArgs) -> OpResult:
    t = quote_ident(a.dataset)
    m = (
        ctx.q(a.dataset, a.measure, kinds=NUMERIC)
        if a.measure and a.agg not in {"count", "count_distinct"}
        else (ctx.q(a.dataset, a.measure) if a.measure else None)
    )
    dims = [ctx.q(a.dataset, g) for g in a.group_by]
    names = [ctx.column(a.dataset, g) for g in a.group_by]
    select, group = list(dims), list(dims)
    if a.time_grain and a.date_column:
        b = ctx.bucket(a.dataset, a.date_column, a.time_grain)
        select.insert(0, f"{b} AS period")
        group.insert(0, b)
        names.insert(0, "period")
    value = _agg_sql(a.agg, m)
    share = (
        ", 100.0 * value / sum(value) OVER () AS share_pct"
        if a.agg in {"sum", "count"} and group
        else ""
    )
    order = {
        "value_desc": "value DESC NULLS LAST",
        "value_asc": "value ASC NULLS LAST",
        "group": ", ".join(str(i + 1) for i in range(len(group))) or "1",
    }[a.sort]
    if a.time_grain:
        order = "1" + (", value DESC" if dims else "")
    inner = f"SELECT {', '.join([*select, f'{value} AS value'])} FROM {t}{ctx.where(a.dataset, a.filters)}"
    if group:
        inner += f" GROUP BY {', '.join(group)}"
    sql = f"SELECT *{share} FROM ({inner}) AS g ORDER BY {order} LIMIT {int(a.limit)}"
    cols, rows, truncated = ctx.fetch(sql)
    label, unit = _measure_label(a.agg, a.measure), _unit_for(a.agg, a.measure)
    facts = Facts("a")
    if not group:
        facts.add(label, rows[0][0] if rows else None, unit, measure=a.measure, agg=a.agg)
    vi = cols.index("value")
    for r in rows[:MAX_FACT_ROWS]:
        key = ", ".join(f"{n}={r[i]}" for i, n in enumerate(names))
        if group:
            facts.add(
                f"{label} for {key}",
                r[vi],
                unit,
                group=dict(zip(names, r[: len(names)], strict=True)),
            )
            if share:
                facts.add(
                    f"share of total {label} for {key}",
                    r[cols.index("share_pct")],
                    "percent",
                    group=dict(zip(names, r[: len(names)], strict=True)),
                )
    if group and a.agg in {"sum", "count"}:
        _, tot, _ = ctx.fetch(f"SELECT {value} FROM {t}{ctx.where(a.dataset, a.filters)}")
        facts.add(f"total {label}", tot[0][0], unit, measure=a.measure, agg=a.agg)
    hint: dict[str, Any] | None = None
    if a.time_grain:
        hint = {
            "type": "line" if not dims else "stacked_bar",
            "x": "period",
            "y": "value",
            "color": names[1] if dims else None,
            "table": "result",
        }
    elif group:
        hint = {
            "type": "bar",
            "x": names[0],
            "y": "value",
            "color": names[1] if len(names) > 1 else None,
            "table": "result",
        }
    notes = (
        ["Result truncated to the requested limit."] if truncated or len(rows) == a.limit else []
    )
    return _result(
        ctx,
        "aggregate",
        a,
        [ResultTable(name="result", columns=cols, rows=rows, truncated=truncated)],
        facts,
        chart_hint=hint,
        notes=notes,
    )


def _period_notes(
    ctx: OpContext, dataset: str, date_col: str, grain: str, where: str
) -> tuple[list[str], Any]:
    q, t = quote_ident(date_col), quote_ident(dataset)
    _, r, _ = ctx.fetch(
        f"SELECT CAST(max(CAST({q} AS DATE)) AS DATE), "
        f"CAST(date_trunc({lit(grain)}, max(CAST({q} AS DATE))) + INTERVAL 1 {grain} - INTERVAL 1 DAY AS DATE) FROM {t}{where}"
    )
    max_date, period_end = r[0]
    notes = []
    partial = max_date is not None and max_date != period_end
    if partial:
        notes.append(
            f"Data ends on {max_date}; the final {grain} is incomplete (period ends {period_end})."
        )
    return notes, (max_date if partial else None)


def trend(ctx: OpContext, a: TrendArgs) -> OpResult:
    t = quote_ident(a.dataset)
    m = (
        ctx.q(a.dataset, a.measure, kinds=NUMERIC)
        if a.measure and a.agg not in {"count", "count_distinct"}
        else (ctx.q(a.dataset, a.measure) if a.measure else None)
    )
    b = ctx.bucket(a.dataset, a.date_column, a.grain)
    dc = ctx.q(a.dataset, a.date_column)
    filters = list(a.filters)
    where = ctx.where(a.dataset, filters)
    extra = []
    if a.start:
        extra.append(f"CAST({dc} AS DATE) >= {lit(a.start.isoformat())}::DATE")
    if a.end:
        extra.append(f"CAST({dc} AS DATE) <= {lit(a.end.isoformat())}::DATE")
    if extra:
        where = (where + " AND " if where else " WHERE ") + " AND ".join(extra)
    g = ctx.q(a.dataset, a.group_by) if a.group_by else None
    gname = ctx.column(a.dataset, a.group_by) if a.group_by else None
    part = f"PARTITION BY {quote_ident(gname)} " if gname is not None else ""
    sel = f"{b} AS period" + (f", {g} AS {quote_ident(gname)}" if gname is not None else "")
    grp = b + (f", {g}" if g else "")
    sql = (
        f"SELECT *, 100.0 * (value - lag(value) OVER ({part}ORDER BY period)) / "
        f"nullif(abs(lag(value) OVER ({part}ORDER BY period)), 0) AS growth_pct "
        f"FROM (SELECT {sel}, {_agg_sql(a.agg, m)} AS value FROM {t}{where} GROUP BY {grp}) AS s "
        f"ORDER BY {'2, ' if g else ''}period"
    )
    cols, rows, truncated = ctx.fetch(sql)
    notes, _ = _period_notes(ctx, a.dataset, ctx.column(a.dataset, a.date_column), a.grain, where)
    label, unit = _measure_label(a.agg, a.measure), _unit_for(a.agg, a.measure)
    facts = Facts("t")
    series: dict[Any, list[list[Any]]] = {}
    for r in rows:
        series.setdefault(r[1] if g else None, []).append(r)
    for key, rs in series.items():
        suffix = f" ({gname}={key})" if g else ""
        for r in rs[-MAX_FACT_ROWS:]:
            facts.add(
                f"{label} in {a.grain} {r[0]}{suffix}",
                r[cols.index("value")],
                unit,
                period=r[0],
                group=key,
            )
            gp = r[cols.index("growth_pct")]
            if gp is not None:
                facts.add(
                    f"{a.grain}-over-{a.grain} growth of {label} in {r[0]}{suffix}",
                    gp,
                    "percent",
                    period=r[0],
                    group=key,
                )
        if len(rs) >= 2 and rs[0][cols.index("value")]:
            first, last = rs[0][cols.index("value")], rs[-1][cols.index("value")]
            facts.add(
                f"change in {label} from {rs[0][0]} to {rs[-1][0]}{suffix}",
                100.0 * (last - first) / abs(first),
                "percent",
                start=rs[0][0],
                end=rs[-1][0],
                group=key,
            )
    hint = {"type": "line", "x": "period", "y": "value", "color": gname, "table": "series"}
    return _result(
        ctx,
        "trend",
        a,
        [ResultTable(name="series", columns=cols, rows=rows, truncated=truncated)],
        facts,
        chart_hint=hint,
        notes=notes,
    )


# ---------------------------------------------------------------- comparisons & rates


def group_compare(ctx: OpContext, a: GroupCompareArgs) -> OpResult:
    from scipy import stats

    t = quote_ident(a.dataset)
    m = ctx.q(a.dataset, a.measure, kinds=NUMERIC)
    gname = ctx.column(a.dataset, a.group_column)
    g = quote_ident(gname)
    filters = list(a.filters)
    where = ctx.where(a.dataset, filters)
    if a.groups:
        vals = ", ".join(lit(v) for v in a.groups)
        where = (where + " AND " if where else " WHERE ") + f"CAST({g} AS VARCHAR) IN ({vals})"
    df = ctx.frame(
        f"SELECT CAST({g} AS VARCHAR) AS grp, {m} AS v FROM {t}{where} AND {m} IS NOT NULL"
        if where
        else f"SELECT CAST({g} AS VARCHAR) AS grp, {m} AS v FROM {t} WHERE {m} IS NOT NULL"
    )
    if df.empty:
        raise OpError("No rows match the comparison")
    df["v"] = df["v"].astype(float)
    groups = {k: v["v"].to_numpy() for k, v in df.groupby("grp", dropna=False)}
    facts = Facts("g")
    rows = []
    for k, v in sorted(groups.items(), key=lambda kv: -float(np.mean(kv[1]))):
        mean, med, std = (
            float(np.mean(v)),
            float(np.median(v)),
            float(np.std(v, ddof=1)) if len(v) > 1 else None,
        )
        rows.append([k, len(v), mean, med, std])
        facts.add(f"mean {a.measure} for {gname}={k}", mean, _unit_for("avg", a.measure), group=k)
        facts.add(f"median {a.measure} for {gname}={k}", med, _unit_for("avg", a.measure), group=k)
        facts.add(f"rows in {gname}={k}", len(v), "count", group=k)
    tables = [ResultTable(name="groups", columns=[gname, "n", "mean", "median", "std"], rows=rows)]
    tests = []
    valid = [v for v in groups.values() if len(v) >= 2]
    notes = [CAUSATION_NOTE]
    if len(valid) == 2:
        w = stats.ttest_ind(valid[0], valid[1], equal_var=False)
        u = stats.mannwhitneyu(valid[0], valid[1], alternative="two-sided")
        tests = [
            ["Welch t-test", float(w.statistic), float(w.pvalue)],
            ["Mann-Whitney U", float(u.statistic), float(u.pvalue)],
        ]
    elif len(valid) > 2:
        f = stats.f_oneway(*valid)
        h = stats.kruskal(*valid)
        tests = [
            ["One-way ANOVA", float(f.statistic), float(f.pvalue)],
            ["Kruskal-Wallis H", float(h.statistic), float(h.pvalue)],
        ]
    else:
        notes.append("Not enough groups with ≥2 observations for a significance test.")
    for name, stat, p in tests:
        facts.add(f"{name} p-value", p, "pvalue", test=name, statistic=stat)
    if tests:
        tables.append(
            ResultTable(name="tests", columns=["test", "statistic", "p_value"], rows=tests)
        )
    return _result(
        ctx,
        "group_compare",
        a,
        tables,
        facts,
        notes=notes,
        chart_hint={"type": "box", "x": gname, "y": a.measure, "table": "groups"},
    )


def rate(ctx: OpContext, a: RateArgs) -> OpResult:
    t = quote_ident(a.dataset)
    col = ctx.column(a.dataset, a.outcome)
    o = quote_ident(col)
    where = ctx.where(a.dataset, a.filters)
    _, distinct, _ = ctx.fetch(
        f"SELECT DISTINCT CAST({o} AS VARCHAR) FROM {t} WHERE {o} IS NOT NULL LIMIT 3"
    )
    allowed = {"0", "1", "true", "false", "0.0", "1.0"}
    if not {str(r[0]).lower() for r in distinct} <= allowed:
        raise OpError(f"'{col}' is not a binary (0/1 or true/false) outcome")
    flag = (
        f"CAST(CAST({o} AS DOUBLE) AS INTEGER)"
        if kind_of(ctx.schema(a.dataset)[col]) == "numeric"
        else f"CAST({o} AS INTEGER)"
    )
    dims = [ctx.q(a.dataset, gb) for gb in a.group_by]
    names = [ctx.column(a.dataset, gb) for gb in a.group_by]
    w2 = (where + " AND " if where else " WHERE ") + f"{o} IS NOT NULL"
    sel = ", ".join(
        [*dims, "count(*) AS n", f"sum({flag}) AS positives", f"100.0 * avg({flag}) AS rate_pct"]
    )
    sql = f"SELECT {sel} FROM {t}{w2}"
    if dims:
        sql += f" GROUP BY {', '.join(dims)} HAVING count(*) >= {int(a.min_group_size)} ORDER BY rate_pct DESC"
    cols, rows, _ = ctx.fetch(sql)
    _, overall, _ = ctx.fetch(f"SELECT count(*), sum({flag}), 100.0 * avg({flag}) FROM {t}{w2}")
    n_all, pos_all, rate_all = overall[0]
    p0 = (pos_all or 0) / n_all if n_all else 0.0
    facts = Facts("r")
    facts.add(f"overall {col} rate", rate_all, "percent")
    facts.add("rows analysed", n_all, "count")
    out = []
    for r in rows[: max(len(rows), 1)]:
        n, pos, pct = r[-3], r[-2], r[-1]
        lo, hi = _wilson(pos or 0, n)
        z = ((pos or 0) / n - p0) / math.sqrt(p0 * (1 - p0) / n) if n and 0 < p0 < 1 else 0.0
        flagged = abs(z) > 3
        out.append([*r, 100 * lo, 100 * hi, z, flagged])
        if dims and len(out) <= MAX_FACT_ROWS:
            key = ", ".join(f"{nm}={r[i]}" for i, nm in enumerate(names))
            grp = dict(zip(names, r[: len(names)], strict=True))
            facts.add(f"{col} rate for {key}", pct, "percent", group=grp)
            facts.add(f"rows for {key}", n, "count", group=grp)
            facts.add(f"{col} count for {key}", pos, "count", group=grp)
    notes = [
        "Groups are flagged as abnormal when their rate is >3 standard errors from the overall rate (normal approximation)."
    ]
    table = ResultTable(
        name="rates",
        columns=[*cols, "ci95_low_pct", "ci95_high_pct", "z_vs_overall", "abnormal"],
        rows=out,
    )
    hint = {"type": "bar", "x": names[0], "y": "rate_pct", "table": "rates"} if names else None
    return _result(ctx, "rate", a, [table], facts, notes=notes, chart_hint=hint)


def _wilson(pos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = pos / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# ---------------------------------------------------------------- correlation & regression


def _numeric_frame(ctx: OpContext, dataset: str, columns: list[str], filters: Any) -> Any:
    qs = [ctx.q(dataset, c, kinds=NUMERIC | {"boolean"}) for c in columns]
    names = [ctx.column(dataset, c) for c in columns]
    sel = ", ".join(
        f"CAST({q} AS DOUBLE) AS {quote_ident(n)}" for q, n in zip(qs, names, strict=True)
    )
    return ctx.frame(
        f"SELECT {sel} FROM {quote_ident(dataset)}{ctx.where(dataset, filters)}"
    ), names


def correlation(ctx: OpContext, a: CorrelationArgs) -> OpResult:
    from scipy import stats

    df, names = _numeric_frame(ctx, a.dataset, a.columns, a.filters)
    fn: Callable[..., Any] = stats.pearsonr if a.method == "pearson" else stats.spearmanr
    facts = Facts("c")
    matrix = [[1.0 if i == j else None for j in range(len(names))] for i in range(len(names))]
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            sub = df[[names[i], names[j]]].dropna()
            if len(sub) < 3 or sub[names[i]].nunique() < 2 or sub[names[j]].nunique() < 2:
                continue
            res = fn(sub[names[i]], sub[names[j]])
            r, p = float(res.statistic), float(res.pvalue)
            matrix[i][j] = matrix[j][i] = r
            pairs.append([names[i], names[j], r, p, len(sub)])
            facts.add(
                f"{a.method} correlation between {names[i]} and {names[j]}",
                r,
                "ratio",
                pair=[names[i], names[j]],
            )
            facts.add(
                f"p-value for correlation between {names[i]} and {names[j]}",
                p,
                "pvalue",
                pair=[names[i], names[j]],
            )
            facts.add(
                f"observations for {names[i]} vs {names[j]}",
                len(sub),
                "count",
                pair=[names[i], names[j]],
            )
    tables = [
        ResultTable(
            name="matrix",
            columns=["column", *names],
            rows=[[n, *row] for n, row in zip(names, matrix, strict=True)],
        ),
        ResultTable(
            name="pairs",
            columns=["x", "y", "r", "p_value", "n"],
            rows=sorted(pairs, key=lambda p: -abs(p[2])),
        ),
    ]
    hint = (
        {"type": "heatmap", "table": "matrix"}
        if len(names) > 2
        else {"type": "scatter", "x": names[0], "y": names[1], "dataset": a.dataset}
    )
    return _result(ctx, "correlation", a, tables, facts, notes=[CAUSATION_NOTE], chart_hint=hint)


def regression(ctx: OpContext, a: RegressionArgs) -> OpResult:
    import statsmodels.api as sm

    df, names = _numeric_frame(ctx, a.dataset, [a.target, *a.features], a.filters)
    df = df.dropna()
    target, feats = names[0], names[1:]
    if len(df) < len(feats) + 3:
        raise OpError("Not enough complete rows for regression")
    model = sm.OLS(df[target], sm.add_constant(df[feats], has_constant="add")).fit()
    ci = model.conf_int()
    facts = Facts("lr")
    rows = []
    for name in ["const", *feats]:
        coef, se, p = float(model.params[name]), float(model.bse[name]), float(model.pvalues[name])
        rows.append([name, coef, se, p, float(ci.loc[name, 0]), float(ci.loc[name, 1])])
        facts.add(f"coefficient of {name} on {target}", coef, "number", term=name)
        facts.add(f"p-value of {name} coefficient", p, "pvalue", term=name)
    facts.add("R-squared", float(model.rsquared), "ratio")
    facts.add("adjusted R-squared", float(model.rsquared_adj), "ratio")
    facts.add("observations", int(model.nobs), "count")
    return _result(
        ctx,
        "regression",
        a,
        [
            ResultTable(
                name="coefficients",
                columns=["term", "coef", "std_err", "p_value", "ci95_low", "ci95_high"],
                rows=rows,
            )
        ],
        facts,
        notes=[
            CAUSATION_NOTE,
            "Ordinary least squares with an intercept; rows with missing values were dropped.",
        ],
        chart_hint={
            "type": "scatter",
            "x": feats[0],
            "y": target,
            "dataset": a.dataset,
            "trendline": True,
        },
    )


# ---------------------------------------------------------------- cohorts & segments


def cohort_retention(ctx: OpContext, a: CohortArgs) -> OpResult:
    t = quote_ident(a.dataset)
    e = ctx.q(a.dataset, a.entity_column)
    b = ctx.bucket(a.dataset, a.date_column, a.grain)
    where = ctx.where(a.dataset, a.filters)
    w2 = (
        where + " AND " if where else " WHERE "
    ) + f"{e} IS NOT NULL AND {ctx.q(a.dataset, a.date_column)} IS NOT NULL"
    sql = (
        f"WITH act AS (SELECT DISTINCT {e} AS entity, {b} AS p FROM {t}{w2}), "
        "coh AS (SELECT entity, min(p) AS cohort FROM act GROUP BY entity), "
        f"j AS (SELECT coh.cohort, datediff({lit(a.grain)}, coh.cohort, act.p) AS k, count(DISTINCT act.entity) AS n "
        "FROM act JOIN coh ON act.entity = coh.entity GROUP BY 1, 2) "
        f"SELECT cohort, k, n FROM j WHERE k <= {int(a.max_periods)} ORDER BY cohort, k"
    )
    _, rows, _ = ctx.fetch(sql)
    by: dict[str, dict[int, int]] = {}
    for cohort, k, n in rows:
        by.setdefault(str(cohort), {})[int(k)] = int(n)
    if a.cohorts:
        wanted = {c[:10] for c in a.cohorts}
        by = {c: v for c, v in by.items() if c[:10] in wanted}
        if not by:
            raise OpError("None of the requested cohorts exist in the data")
    facts = Facts("co")
    header = ["cohort", "size", *[f"{a.grain}_{k}" for k in range(a.max_periods + 1)]]
    out = []
    for cohort, ks in by.items():
        size = ks.get(0, 0)
        pct = [100.0 * ks[k] / size if size and k in ks else None for k in range(a.max_periods + 1)]
        out.append([cohort, size, *pct])
        facts.add(f"size of cohort {cohort}", size, "count", cohort=cohort)
        for k, v in enumerate(pct):
            if v is not None and k > 0 and len(facts.items) < 400:
                facts.add(
                    f"{a.grain} {k} retention of cohort {cohort}",
                    v,
                    "percent",
                    cohort=cohort,
                    period=k,
                )
    notes = [
        f"Retention = share of the cohort's entities active k {a.grain}s after their first {a.grain}.",
        "Recent cohorts have fewer observable periods; blank cells are not zero.",
    ]
    return _result(
        ctx,
        "cohort_retention",
        a,
        [ResultTable(name="retention", columns=header, rows=out)],
        facts,
        notes=notes,
        chart_hint={"type": "heatmap", "table": "retention", "value_suffix": "%"},
    )


def segment(ctx: OpContext, a: SegmentArgs) -> OpResult:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    df, names = _numeric_frame(ctx, a.dataset, a.features, a.filters)
    df = df.dropna()
    if len(df) < a.k * 5:
        raise OpError(f"Need at least {a.k * 5} complete rows to form {a.k} segments")
    x = StandardScaler().fit_transform(df[names].to_numpy())
    km = KMeans(n_clusters=a.k, n_init=10, random_state=0).fit(x)
    labels = km.labels_
    sample = min(len(df), 5000)
    sil = float(silhouette_score(x, labels, sample_size=sample, random_state=0))
    df = df.assign(segment=labels)
    facts = Facts("s")
    facts.add("silhouette score", sil, "ratio")
    facts.add("rows clustered", len(df), "count")
    rows = []
    order = df.groupby("segment").size().sort_values(ascending=False).index
    for rank, seg in enumerate(order):
        part = df[df["segment"] == seg]
        means = [float(part[n].mean()) for n in names]
        rows.append([f"S{rank + 1}", len(part), 100.0 * len(part) / len(df), *means])
        facts.add(f"size of segment S{rank + 1}", len(part), "count", segment=f"S{rank + 1}")
        facts.add(
            f"share of rows in segment S{rank + 1}",
            100.0 * len(part) / len(df),
            "percent",
            segment=f"S{rank + 1}",
        )
        for n, mval in zip(names, means, strict=True):
            facts.add(
                f"mean {n} in segment S{rank + 1}",
                mval,
                _unit_for("avg", n),
                segment=f"S{rank + 1}",
            )
    notes = [
        "K-means on standardised features (seed 0); segment labels are ordered by size.",
        f"k={a.k} was chosen explicitly, not optimised.",
    ]
    return _result(
        ctx,
        "segment",
        a,
        [
            ResultTable(
                name="segments",
                columns=["segment", "n", "share_pct", *[f"mean_{n}" for n in names]],
                rows=rows,
            )
        ],
        facts,
        notes=notes,
        chart_hint={"type": "bar", "x": "segment", "y": "n", "table": "segments"},
    )


def outliers(ctx: OpContext, a: OutlierArgs) -> OpResult:
    col = ctx.column(a.dataset, a.column, kinds=NUMERIC)
    gname = ctx.column(a.dataset, a.group_by) if a.group_by else None
    t, where = quote_ident(a.dataset), ctx.where(a.dataset, a.filters)
    w2 = (where + " AND " if where else " WHERE ") + f"{quote_ident(col)} IS NOT NULL"
    df = ctx.frame(f"SELECT * FROM {t}{w2}")
    df[col] = df[col].astype(float)
    keys = df.groupby(gname) if gname else [(None, df)]
    flagged_parts = []
    summary = []
    for key, part in keys:
        if len(part) < a.min_group_size:
            continue
        v = part[col]
        if a.method == "iqr":
            q1, q3 = v.quantile(0.25), v.quantile(0.75)
            lo, hi = q1 - a.threshold * (q3 - q1), q3 + a.threshold * (q3 - q1)
        else:
            mu, sd = v.mean(), v.std(ddof=1)
            lo, hi = mu - a.threshold * sd, mu + a.threshold * sd
        mask = (v < lo) | (v > hi)
        flagged_parts.append(part[mask])
        summary.append(
            [
                key if gname else "all",
                len(part),
                int(mask.sum()),
                100.0 * mask.mean(),
                float(lo),
                float(hi),
            ]
        )
    import pandas as pd

    flagged = pd.concat(flagged_parts) if flagged_parts else df.iloc[0:0]
    flagged = flagged.reindex(
        flagged[col].sub(df[col].median()).abs().sort_values(ascending=False).index
    ).head(100)
    facts = Facts("o")
    facts.add(f"outliers in {col}", int(sum(s[2] for s in summary)), "count")
    facts.add("rows examined", int(sum(s[1] for s in summary)), "count")
    for s in summary[:MAX_FACT_ROWS]:
        facts.add(f"outliers in {col} for {gname or 'all rows'}={s[0]}", s[2], "count", group=s[0])
        facts.add(f"outlier share for {gname or 'all rows'}={s[0]}", s[3], "percent", group=s[0])
    tables = [
        ResultTable(
            name="summary",
            columns=[
                gname or "scope",
                "n",
                "outliers",
                "outlier_pct",
                "lower_fence",
                "upper_fence",
            ],
            rows=sorted(summary, key=lambda s: -s[3]),
        ),
        ResultTable(
            name="flagged_rows",
            columns=list(flagged.columns),
            rows=[
                [_clean(x) if not isinstance(x, str) else x for x in r]
                for r in flagged.astype(object).where(flagged.notna(), None).to_numpy().tolist()
            ],
        ),
    ]
    rule = f"{a.threshold} x IQR" if a.method == "iqr" else f"|z| > {a.threshold}"
    return _result(
        ctx,
        "outliers",
        a,
        tables,
        facts,
        notes=[f"Outlier rule: {rule}{' within each ' + gname if gname else ''}."],
        chart_hint={"type": "box", "x": gname, "y": col, "dataset": a.dataset},
    )


# ---------------------------------------------------------------- forecasting

SEASON = {"day": 7, "week": 52, "month": 12, "quarter": 4}


def forecast(ctx: OpContext, a: ForecastArgs) -> OpResult:
    import pandas as pd
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    series = trend(
        ctx,
        TrendArgs(
            dataset=a.dataset,
            filters=a.filters,
            measure=a.measure,
            agg=a.agg,
            date_column=a.date_column,
            grain=a.grain,
        ),
    )
    notes = list(series.notes)
    rows = series.tables[0].rows
    if notes and any("incomplete" in n for n in notes):
        rows = rows[:-1]
        notes.append("The incomplete final period was excluded from model fitting.")
    if len(rows) < 8:
        raise OpError("Forecasting needs at least 8 complete periods")
    idx = pd.to_datetime([r[0] for r in rows])
    y = pd.Series([float(r[1]) for r in rows], index=idx)
    season = SEASON[a.grain]
    seasonal = "add" if len(y) >= 2 * season else None

    def fit(s: Any) -> Any:
        return ExponentialSmoothing(
            s.to_numpy(),
            trend="add",
            seasonal=seasonal,
            seasonal_periods=season if seasonal else None,
            initialization_method="estimated",
        ).fit()

    holdout = max(1, min(a.horizon, len(y) // 4))
    bt = fit(y.iloc[:-holdout]).forecast(holdout)
    actual = y.iloc[-holdout:].to_numpy()
    mae = float(np.mean(np.abs(actual - bt)))
    nz = actual != 0
    mape = float(np.mean(np.abs((actual[nz] - bt[nz]) / actual[nz])) * 100) if nz.any() else None
    model = fit(y)
    fc = model.forecast(a.horizon)
    resid_sd = float(np.std(y.to_numpy() - model.fittedvalues, ddof=1))
    freq = {"day": "D", "week": "W-MON", "month": "MS", "quarter": "QS"}[a.grain]
    future = pd.date_range(idx[-1], periods=a.horizon + 1, freq=freq)[1:]
    facts = Facts("f")
    facts.add("backtest MAE", mae, _unit_for(a.agg, a.measure), holdout_periods=holdout)
    if mape is not None:
        facts.add("backtest MAPE", mape, "percent", holdout_periods=holdout)
    out = [[str(d.date()), float(v), "actual", None, None] for d, v in y.items()]
    for h, (d, v) in enumerate(zip(future, fc, strict=True), start=1):
        band = 1.96 * resid_sd * math.sqrt(h)
        out.append([str(d.date()), float(v), "forecast", float(v - band), float(v + band)])
        facts.add(
            f"forecast for {d.date()}",
            float(v),
            _unit_for(a.agg, a.measure),
            period=str(d.date()),
            horizon=h,
        )
    notes += [
        f"Holt-Winters exponential smoothing (additive trend{', additive seasonality' if seasonal else ''}).",
        f"Backtest: fitted on all but the last {holdout} periods and compared with actuals.",
        "Bands are approximate +/-1.96 * sd * sqrt(h) from in-sample residuals, not exact prediction intervals.",
    ]
    return _result(
        ctx,
        "forecast",
        a,
        [
            ResultTable(
                name="forecast", columns=["period", "value", "kind", "lower", "upper"], rows=out
            )
        ],
        facts,
        notes=notes,
        chart_hint={"type": "forecast", "x": "period", "y": "value", "table": "forecast"},
    )


REGISTRY: dict[str, Callable[[OpContext, Any], OpResult]] = {
    "describe": describe,
    "missing_values": missing_values,
    "aggregate": aggregate,
    "trend": trend,
    "group_compare": group_compare,
    "rate": rate,
    "correlation": correlation,
    "regression": regression,
    "cohort_retention": cohort_retention,
    "segment": segment,
    "outliers": outliers,
    "forecast": forecast,
}


def run_operation(ctx: OpContext, args: Any) -> OpResult:
    return REGISTRY[args.op](ctx, args)
