from __future__ import annotations

import pytest

from insightforge.sql.validator import SQLRejected, validate_sql

TABLES = {"orders", "customers"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT region, sum(revenue) FROM orders GROUP BY region",
        "WITH m AS (SELECT date_trunc('month', order_date) AS m, revenue FROM orders) "
        "SELECT m, sum(revenue) FROM m GROUP BY 1 ORDER BY 1",
        "SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id WHERE c.tier = 'gold'",
        "SELECT * FROM orders UNION ALL SELECT * FROM orders",
        "SELECT region, revenue, rank() OVER (PARTITION BY region ORDER BY revenue) FROM orders",
        "select count(*) from ORDERS",
    ],
)
def test_accepts_read_only_analytics(sql: str) -> None:
    v = validate_sql(sql, TABLES)
    assert v.tables <= TABLES


@pytest.mark.parametrize(
    ("sql", "fragment"),
    [
        ("DROP TABLE orders", "Only read-only"),
        ("DELETE FROM orders", "Only read-only"),
        ("INSERT INTO orders VALUES (1)", "Only read-only"),
        ("UPDATE orders SET revenue = 0", "Only read-only"),
        ("CREATE TABLE x AS SELECT * FROM orders", "Only read-only"),
        ("SELECT 1 FROM orders; DROP TABLE orders", "Exactly one"),
        ("ATTACH '/etc/passwd' AS p", ""),
        ("COPY orders TO '/tmp/x.csv'", ""),
        ("INSTALL httpfs", ""),
        ("LOAD httpfs", ""),
        ("PRAGMA database_list", ""),
        ("SET enable_external_access = true", ""),
        ("SELECT * FROM read_csv('/etc/passwd')", "not allowed"),
        ("SELECT * FROM read_parquet('s3://bucket/x.parquet')", "not allowed"),
        ("SELECT * FROM '/etc/passwd'", ""),
        ("SELECT * FROM 'https://evil.example/x.csv'", ""),
        ("SELECT getenv('HOME') FROM orders", "getenv"),
        ("SELECT * FROM glob('/Users/*')", "not allowed"),
        ("SELECT * FROM secrets", "Unknown table"),
        ("SELECT * FROM main.orders", "qualified"),
        ("SELECT * FROM other_db.main.orders", "qualified"),
        ("SELECT * FROM duckdb_settings()", "not allowed"),
        ("SELECT * FROM orders WHERE id IN (SELECT id FROM sqlite_scan('x.db', 't'))", "allowed"),
        ("SELECT query('DROP TABLE orders') FROM orders", "not allowed"),
        ("SELECT 1", "at least one"),
        ("", "empty"),
        ("SELEC * FRM orders", ""),
    ],
)
def test_rejects_unsafe_or_invalid_sql(sql: str, fragment: str) -> None:
    with pytest.raises(SQLRejected) as info:
        validate_sql(sql, TABLES)
    assert fragment in str(info.value)


def test_cte_names_are_not_treated_as_unknown_tables() -> None:
    v = validate_sql("WITH x AS (SELECT * FROM orders) SELECT * FROM x", TABLES)
    assert v.tables == {"orders"}


def test_cte_cannot_smuggle_file_reads() -> None:
    with pytest.raises(SQLRejected):
        validate_sql("WITH x AS (SELECT * FROM read_text('/etc/hosts')) SELECT * FROM x", TABLES)


def test_oversized_sql_rejected() -> None:
    with pytest.raises(SQLRejected, match="exceeds"):
        validate_sql("SELECT * FROM orders WHERE " + " OR ".join(["1=1"] * 6000), TABLES)
