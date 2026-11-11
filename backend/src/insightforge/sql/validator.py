"""Static SQL policy enforced on the parsed AST (SQLGlot, DuckDB dialect).

Rejecting here gives fast, explainable errors. It is *not* the only line of defence:
accepted queries still run inside the sandbox worker on a locked DuckDB connection.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

MAX_SQL_CHARS = 20_000

# Statement / clause node types that are never allowed anywhere in the tree.
_FORBIDDEN_NODES: tuple[type[exp.Expr], ...] = tuple(
    getattr(exp, name)
    for name in (
        "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "TruncateTable",
        "Command", "Copy", "Pragma", "Attach", "Detach", "Use", "Set", "Transaction",
        "Commit", "Rollback", "Grant", "Revoke", "Install", "Load", "Export", "Into",
        "Summarize", "Describe", "LoadData", "Kill", "Show",
    )
    if hasattr(exp, name)
)  # fmt: skip

# File, network, catalog and system access. Matched case-insensitively against every
# function name, whether SQLGlot recognises it or treats it as anonymous.
_DENY_FUNCTION_PATTERNS = re.compile(
    r"^(read_\w+|scan_\w+|\w+_scan|glob|getenv|sniff_csv|parquet_\w+|duckdb_\w+|pragma_\w*"
    r"|query|query_table|which_secret|load|install|http\w*|iceberg_\w+|delta_\w+|current_setting"
    r"|enable_\w+|disable_\w+|checkpoint|force_checkpoint|sqlite_\w+|postgres_\w+|mysql_\w+"
    r"|json_execute_serialized_sql|from_substrait\w*|get_substrait\w*|system|shell|exec\w*)$",
    re.IGNORECASE,
)


class SQLRejected(ValueError):
    pass


@dataclass
class ValidatedSQL:
    sql: str  # normalized SQL that will actually be executed
    tables: set[str] = field(default_factory=set)
    has_limit: bool = False


def _function_names(node: exp.Func) -> set[str]:
    names = {node.sql_name().lower()}
    if isinstance(node, exp.Anonymous):
        names.add(str(node.this).lower())
    for key in ("name",):
        val = getattr(node, key, None)
        if isinstance(val, str) and val:
            names.add(val.lower())
    return names


JoinKey = tuple[str, str, str, str]  # (table, column, table, column), lower-case


def _check_joins(tree: exp.Expr, tables: set[str], relationships: Collection[JoinKey]) -> None:
    """Joins between two base dataset tables must follow a declared relationship.

    This is an analytical-correctness guard (prevents nonsense joins), not a security
    boundary: joins whose sides are CTEs or subqueries are not constrained.
    """
    rels = {(a, b, c, d) for a, b, c, d in relationships} | {
        (c, d, a, b) for a, b, c, d in relationships
    }
    for select in tree.find_all(exp.Select):
        joins = select.args.get("joins") or []
        if not joins:
            continue
        sources = [select.args.get("from_") or select.args.get("from")]
        alias: dict[str, str] = {}
        for src in [*(s.this for s in sources if s is not None), *(j.this for j in joins)]:
            if isinstance(src, exp.Table) and src.name.lower() in tables:
                alias[(src.alias_or_name).lower()] = src.name.lower()
        for j in joins:
            right = j.this
            if (
                not (isinstance(right, exp.Table) and right.name.lower() in tables)
                or len(alias) < 2
            ):
                continue
            if j.args.get("kind", "").upper() == "CROSS" or (
                j.args.get("on") is None and not j.args.get("using")
            ):
                raise SQLRejected("Cross joins between datasets are not allowed")
            pairs: set[JoinKey] = set()
            if j.args.get("using"):
                rname = right.name.lower()
                for ident in j.args["using"]:
                    col = ident.name.lower()
                    pairs |= {(t, col, rname, col) for t in alias.values() if t != rname}
            for eq in (j.args.get("on") or exp.true()).find_all(exp.EQ):
                lc, rc = eq.left, eq.right
                if (
                    isinstance(lc, exp.Column)
                    and isinstance(rc, exp.Column)
                    and lc.table
                    and rc.table
                ):
                    lt, rt = alias.get(lc.table.lower()), alias.get(rc.table.lower())
                    if lt and rt:
                        pairs.add((lt, lc.name.lower(), rt, rc.name.lower()))
            if not pairs & rels:
                raise SQLRejected(
                    f"Join with '{right.name}' does not follow a declared dataset relationship"
                )


def validate_sql(
    sql: str, allowed_tables: Collection[str], relationships: Collection[JoinKey] | None = None
) -> ValidatedSQL:
    if not sql or not sql.strip():
        raise SQLRejected("Query is empty")
    if len(sql) > MAX_SQL_CHARS:
        raise SQLRejected(f"Query exceeds {MAX_SQL_CHARS} characters")
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except ParseError as exc:
        first = exc.errors[0]["description"] if exc.errors else "syntax error"
        raise SQLRejected(f"Could not parse SQL: {first}") from exc
    if len(statements) != 1:
        raise SQLRejected("Exactly one SQL statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise SQLRejected(f"Only read-only SELECT queries are allowed (got {tree.key.upper()})")

    allowed = {t.lower() for t in allowed_tables}
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    tables: set[str] = set()

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise SQLRejected(f"{node.key.upper()} is not allowed")
        if isinstance(node, exp.Func):
            names = _function_names(node)
            bad = sorted(n for n in names if _DENY_FUNCTION_PATTERNS.match(n))
            if bad:
                raise SQLRejected(f"Function {bad[0]} is not allowed")
        if isinstance(node, exp.Table):
            if not isinstance(node.this, exp.Identifier):
                raise SQLRejected("Table functions are not allowed in FROM")
            if node.args.get("db") or node.args.get("catalog"):
                raise SQLRejected("Schema- or catalog-qualified tables are not allowed")
            name = node.name.lower()
            if name in cte_names:
                continue
            if name not in allowed:
                raise SQLRejected(f"Unknown table '{node.name}'")
            tables.add(name)
        if isinstance(node, exp.Literal) and node.is_string:
            # string literals used as FROM targets are caught above; also block file URLs
            value = node.this.lower()
            if value.startswith(("http://", "https://", "s3://", "gs://", "file:", "az://")):
                raise SQLRejected("URLs are not allowed in queries")

    if not tables and not cte_names:
        # constant-only queries are harmless but useless for analysis
        raise SQLRejected("Query must read from at least one dataset table")

    if relationships is not None:
        _check_joins(tree, allowed, relationships)

    return ValidatedSQL(
        sql=tree.sql(dialect="duckdb"),
        tables=tables,
        has_limit=tree.args.get("limit") is not None,
    )
