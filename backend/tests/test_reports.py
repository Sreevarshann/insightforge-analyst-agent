from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from insightforge.reports.render import table_csv

CSV = b"region,revenue\n" + b"East,10\nWest,20\n=HYPERLINK(1),5\n" * 4


def _analysis(client: TestClient) -> dict:  # type: ignore[type-arg]
    client.post("/api/datasets", files={"file": ("orders.csv", CSV)})
    return client.post(
        "/api/analyses", json={"question": "total revenue by region <script>alert(1)</script>"}
    ).json()


def test_markdown_report_contains_reproducible_record(client: TestClient) -> None:
    a = _analysis(client)
    md = client.get(f"/api/analyses/{a['id']}/report", params={"format": "md"}).text
    assert md.startswith("# ") and "## Step 1" in md and "```sql" in md
    assert "Dataset versions:" in md and a["dataset_versions"][0] in md


def test_html_report_escapes_text_and_sets_csp(client: TestClient) -> None:
    a = _analysis(client)
    res = client.get(f"/api/analyses/{a['id']}/report", params={"format": "html", "download": True})
    assert res.headers["content-type"].startswith("text/html")
    assert "attachment" in res.headers["content-disposition"]
    assert "default-src 'none'" in res.headers["content-security-policy"]
    assert "<script>alert(1)</script>" not in res.text and "&lt;script&gt;" in res.text
    assert "cdn.plot.ly" in res.text  # chart rendered from the stored validated spec


def test_csv_export_and_formula_neutralisation(client: TestClient) -> None:
    a = _analysis(client)
    res = client.get(f"/api/analyses/{a['id']}/export.csv", params={"step": 1, "table": "result"})
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows[0][0] == "region"
    assert any(r[0] == "'=HYPERLINK(1)" for r in rows[1:])
    assert (
        client.get(f"/api/analyses/{a['id']}/export.csv", params={"table": "nope"}).status_code
        == 404
    )


def test_table_csv_handles_nulls() -> None:
    # a lone empty field is quoted so the row is not mistaken for a blank line
    assert table_csv({"columns": ["a", "b"], "rows": [[None, 1]]}).splitlines() == ["a,b", ",1"]
