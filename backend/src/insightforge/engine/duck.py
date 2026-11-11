"""Hardened DuckDB connections over registered Parquet files.

This is defence in depth *inside* a process. It is not the security boundary for
untrusted SQL on its own — that is the sandbox worker (see ``insightforge.sql.sandbox``),
which additionally applies OS resource limits and runs in a separate process.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import duckdb


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def locked_connection(
    views: Mapping[str, Path], *, memory_limit_mb: int = 1024, threads: int = 2
) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with one read-only view per Parquet file and everything else off.

    After this returns, the connection cannot read other files, use the network, install
    or load extensions, or change its own configuration.
    """
    con = duckdb.connect(
        ":memory:",
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "allow_community_extensions": False,
            "memory_limit": f"{memory_limit_mb}MB",
            "threads": threads,
        },
    )
    try:
        paths = [str(p.resolve()) for p in views.values()]
        for name, path in views.items():
            literal = quote_literal(str(path.resolve()))
            con.execute(
                f"CREATE VIEW {quote_ident(name)} AS SELECT * FROM read_parquet({literal})"  # noqa: S608
            )
        allowed = "[" + ", ".join(quote_literal(p) for p in paths) + "]"
        con.execute(f"SET allowed_paths = {allowed}")
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
    except BaseException:
        con.close()
        raise
    return con
