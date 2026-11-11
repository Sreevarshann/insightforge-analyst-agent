from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from insightforge.demo.generate import generate, write
from insightforge.sql.validator import SQLRejected, validate_sql


def test_generator_is_deterministic_and_has_planted_patterns() -> None:
    a, b = generate(), generate()
    for k in a:
        pd.testing.assert_frame_equal(a[k], b[k])
    o, s = a["orders"], a["subscriptions"]
    refund = o.groupby("product_id").refunded.mean()
    assert refund.idxmax() == "P02" and refund["P02"] > 2 * refund.drop("P02").max()
    churn = s.groupby("plan").churned.mean()
    assert churn.idxmax() == "Starter"
    assert o.duplicated().sum() > 0 and (o.quantity < 0).sum() == 6
    assert a["customers"].region.isna().sum() > 0


def upload_demo(client: TestClient, tmp_path: Path) -> dict[str, dict]:  # type: ignore[type-arg]
    out = {}
    for p in write(tmp_path / "demo"):
        out[p.stem] = client.post("/api/datasets", files={"file": (p.name, p.read_bytes())}).json()[
            0
        ]
    return out


def test_relationship_validation_and_cardinality(client: TestClient, tmp_path: Path) -> None:
    ds = upload_demo(client, tmp_path)
    res = client.post(
        "/api/relationships",
        json={
            "left_dataset_id": ds["orders"]["id"],
            "left_column": "customer_id",
            "right_dataset_id": ds["customers"]["id"],
            "right_column": "customer_id",
        },
    )
    assert res.status_code == 201 and res.json()["cardinality"] == "many_to_one"
    bad = client.post(
        "/api/relationships",
        json={
            "left_dataset_id": ds["orders"]["id"],
            "left_column": "product_id",
            "right_dataset_id": ds["customers"]["id"],
            "right_column": "customer_id",
        },
    )
    assert bad.status_code == 422 and "match" in bad.json()["detail"]
    types = client.post(
        "/api/relationships",
        json={
            "left_dataset_id": ds["orders"]["id"],
            "left_column": "quantity",
            "right_dataset_id": ds["customers"]["id"],
            "right_column": "customer_id",
        },
    )
    assert types.status_code == 422


def test_joins_must_follow_declared_relationships(client: TestClient, tmp_path: Path) -> None:
    ds = upload_demo(client, tmp_path)
    sql = "SELECT c.segment, sum(o.revenue) FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY 1"
    assert (
        client.post("/api/query", json={"sql": sql})
        .json()["detail"]["message"]
        .startswith("Join with")
    )
    client.post(
        "/api/relationships",
        json={
            "left_dataset_id": ds["orders"]["id"],
            "left_column": "customer_id",
            "right_dataset_id": ds["customers"]["id"],
            "right_column": "customer_id",
        },
    )
    res = client.post("/api/query", json={"sql": sql})
    assert res.status_code == 200 and len(res.json()["rows"]) == 3


REL = [("orders", "customer_id", "customers", "customer_id")]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders o JOIN customers c ON o.region = c.region",
        "SELECT * FROM orders, customers",
        "SELECT * FROM orders CROSS JOIN customers",
        "SELECT * FROM orders JOIN customers USING (region)",
    ],
)
def test_undeclared_joins_rejected(sql: str) -> None:
    with pytest.raises(SQLRejected):
        validate_sql(sql, {"orders", "customers"}, REL)


def test_declared_join_variants_accepted() -> None:
    validate_sql(
        "SELECT * FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id",
        {"orders", "customers"},
        REL,
    )
    validate_sql(
        "SELECT * FROM orders JOIN customers USING (customer_id)", {"orders", "customers"}, REL
    )
