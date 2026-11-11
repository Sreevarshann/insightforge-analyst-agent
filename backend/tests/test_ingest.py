from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from insightforge.ingest import formats
from insightforge.ingest.normalize import normalize_columns, to_identifier, unique_identifier

CSV = (
    b"order_id,region,revenue,order date\n"
    b"1,East,10.5,2025-01-03\n2,West,20,2025-01-04\n3,East,,2025-02-01\n"
)


def upload(client: TestClient, name: str, data: bytes, **form: str):  # type: ignore[no-untyped-def]
    return client.post("/api/datasets", files={"file": (name, data)}, data=form)


def test_csv_upload_infers_types_and_counts(client: TestClient) -> None:
    res = upload(client, "orders.csv", CSV)
    assert res.status_code == 201, res.text
    (ds,) = res.json()
    assert ds["table_name"] == "orders"
    assert ds["current"]["row_count"] == 3
    types = {c["name"]: c["type"] for c in ds["columns"]}
    assert types["order_id"] == "BIGINT"
    assert types["revenue"] == "DOUBLE"
    assert types["order date"] == "DATE"


def test_tsv_upload(client: TestClient) -> None:
    res = upload(client, "x.tsv", b"a\tb\n1\thello\n2\tworld\n")
    assert res.status_code == 201
    assert [c["name"] for c in res.json()[0]["columns"]] == ["a", "b"]


def test_parquet_upload(client: TestClient) -> None:
    buf = io.BytesIO()
    pq.write_table(pa.table({"x": [1, 2, 3], "y": ["a", "b", "c"]}), buf)
    res = upload(client, "data.parquet", buf.getvalue())
    assert res.status_code == 201
    assert res.json()[0]["current"]["row_count"] == 3


def test_xlsx_upload_creates_dataset_per_sheet(client: TestClient) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Q1"
    ws.append(["product", "units"])
    ws.append(["A", 5])
    ws.append(["B", 7])
    ws2 = wb.create_sheet("Q2")
    ws2.append(["product", "units"])
    ws2.append(["A", 9])
    buf = io.BytesIO()
    wb.save(buf)
    res = upload(client, "sales.xlsx", buf.getvalue())
    assert res.status_code == 201, res.text
    names = sorted(d["display_name"] for d in res.json())
    assert names == ["sales · Q1", "sales · Q2"]
    rows = {d["display_name"]: d["current"]["row_count"] for d in res.json()}
    assert rows["sales · Q1"] == 2


def test_sqlite_upload_reads_tables_read_only(client: TestClient, tmp_path: Path) -> None:
    db = tmp_path / "shop.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE customers (id INTEGER, name TEXT)")
    con.executemany("INSERT INTO customers VALUES (?, ?)", [(1, "a"), (2, "b")])
    con.commit()
    con.close()
    res = upload(client, "shop.sqlite", db.read_bytes())
    assert res.status_code == 201, res.text
    assert res.json()[0]["current"]["row_count"] == 2


@pytest.mark.parametrize(
    ("name", "data", "fragment"),
    [
        ("evil.exe", b"MZ\x90\x00", "Unsupported file type"),
        ("fake.xlsx", b"not a zip at all", "does not match"),
        ("fake.parquet", b"hello world!", "does not match"),
        ("fake.sqlite", b"hello", "does not match"),
        ("bin.csv", b"a,b\n\x00\x01\x02", "binary"),
        ("empty.csv", b"", "empty"),
    ],
)
def test_rejects_invalid_uploads(client: TestClient, name: str, data: bytes, fragment: str) -> None:
    res = upload(client, name, data)
    assert res.status_code == 422
    assert fragment in res.json()["detail"]


def test_size_limit_enforced(tmp_path: Path) -> None:
    from insightforge.config import Settings
    from insightforge.main import create_app

    s = Settings(environment="test", data_dir=tmp_path / "v", max_upload_bytes=100)
    with TestClient(create_app(s)) as c:
        res = upload(c, "big.csv", b"a\n" + b"1\n" * 200)
    assert res.status_code == 422 and "limit" in res.json()["detail"]
    assert not any((tmp_path / "v" / "tmp").iterdir())  # temp file cleaned up


def test_xlsx_decompression_bomb_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(formats, "MAX_XLSX_UNCOMPRESSED", 1000)
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    for i in range(200):
        ws.append(["x" * 20, i])
    buf = io.BytesIO()
    wb.save(buf)
    res = upload(client, "bomb.xlsx", buf.getvalue())
    assert res.status_code == 422 and "unsafe size" in res.json()["detail"]


def test_path_traversal_filename_is_neutralized(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    res = upload(client, "../../../etc/orders.csv", CSV)
    assert res.status_code == 201
    assert res.json()[0]["current"]["source_name"] == "orders.csv"
    assert not (settings.data_dir.parent / "etc").exists()


def test_parse_error_does_not_leak_content(client: TestClient) -> None:
    secret = b"TOPSECRET"
    data = b"PAR1" + secret + b"PAR1"
    res = upload(client, "bad.parquet", data)
    assert res.status_code == 422
    assert "TOPSECRET" not in res.text


def test_versions_and_identical_reupload(client: TestClient) -> None:
    ds = upload(client, "orders.csv", CSV).json()[0]
    v2 = CSV + b"4,North,5,2025-03-01\n"
    res = client.post(f"/api/datasets/{ds['id']}/versions", files={"file": ("orders.csv", v2)})
    assert res.status_code == 201
    assert res.json()["current"]["version"] == 2 and res.json()["current"]["row_count"] == 4
    dup = client.post(f"/api/datasets/{ds['id']}/versions", files={"file": ("orders.csv", v2)})
    assert dup.status_code == 422
    versions = client.get(f"/api/datasets/{ds['id']}/versions").json()
    assert [v["version"] for v in versions] == [1, 2]
    old = client.get(f"/api/datasets/{ds['id']}/preview", params={"version": 1}).json()
    assert old["total_rows"] == 3


def test_table_names_are_unique(client: TestClient) -> None:
    a = upload(client, "orders.csv", CSV).json()[0]
    b = upload(client, "orders.csv", CSV).json()[0]
    assert (a["table_name"], b["table_name"]) == ("orders", "orders_2")


def test_preview_sort_search_paginate(client: TestClient) -> None:
    ds = upload(client, "orders.csv", CSV).json()[0]
    url = f"/api/datasets/{ds['id']}/preview"
    r = client.get(url, params={"sort": "revenue", "order": "desc"}).json()
    assert [row[2] for row in r["rows"]] == [20.0, 10.5, None]
    r = client.get(url, params={"search": "east"}).json()
    assert r["total_rows"] == 2
    r = client.get(url, params={"limit": 1, "offset": 1}).json()
    assert len(r["rows"]) == 1 and r["rows"][0][0] == 2
    assert client.get(url, params={"sort": "x; DROP TABLE t"}).status_code == 422


def test_preview_search_is_parameterized(client: TestClient) -> None:
    ds = upload(client, "orders.csv", CSV).json()[0]
    r = client.get(f"/api/datasets/{ds['id']}/preview", params={"search": "' OR 1=1 --"})
    assert r.status_code == 200 and r.json()["total_rows"] == 0


def test_delete_removes_files(client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
    ds = upload(client, "orders.csv", CSV).json()[0]
    assert (settings.datasets_dir / ds["id"]).is_dir()
    assert client.delete(f"/api/datasets/{ds['id']}").status_code == 204
    assert not (settings.datasets_dir / ds["id"]).exists()
    assert client.get(f"/api/datasets/{ds['id']}").status_code == 404


def test_identifier_normalization() -> None:
    assert to_identifier("Order Lines (2025)") == "order_lines_2025"
    assert to_identifier("2025 sales") == "t_2025_sales"
    assert to_identifier("select") == "select_"
    assert to_identifier("!!!") == "t"
    assert unique_identifier("a", {"a", "a_2"}) == "a_3"
    t = normalize_columns(pa.table({"  x ": [1], "Unnamed: 1": [2]}))
    assert t.column_names == ["x", "column_2"]
