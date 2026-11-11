from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from insightforge.engine.duck import locked_connection


@pytest.fixture
def parquet(tmp_path: Path) -> Path:
    p = tmp_path / "it's.parquet"  # quote in name exercises literal escaping
    pq.write_table(pa.table({"x": [1, 2, 3]}), p)
    return p


def test_registered_view_is_queryable(parquet: Path) -> None:
    con = locked_connection({"t": parquet})
    assert con.execute("SELECT sum(x) FROM t").fetchone() == (6,)


def test_other_files_are_not_readable(parquet: Path, tmp_path: Path) -> None:
    other = tmp_path / "secret.csv"
    other.write_text("a\n1\n")
    con = locked_connection({"t": parquet})
    with pytest.raises(duckdb.Error):
        con.execute(f"SELECT * FROM read_csv('{other}')").fetchall()


def test_configuration_is_locked(parquet: Path) -> None:
    con = locked_connection({"t": parquet})
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")


def test_extensions_cannot_be_installed(parquet: Path) -> None:
    con = locked_connection({"t": parquet})
    with pytest.raises(duckdb.Error):
        con.execute("INSTALL httpfs")


def test_copy_to_filesystem_blocked(parquet: Path, tmp_path: Path) -> None:
    con = locked_connection({"t": parquet})
    with pytest.raises(duckdb.Error):
        con.execute(f"COPY t TO '{tmp_path / 'out.csv'}'")
    assert not (tmp_path / "out.csv").exists()
