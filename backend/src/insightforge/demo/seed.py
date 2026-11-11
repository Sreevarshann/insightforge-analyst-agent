"""Load the synthetic demo CSVs as datasets (flagged is_demo) and declare relationships."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from sqlalchemy import select

from insightforge.config import Settings, get_settings
from insightforge.db.models import Dataset
from insightforge.db.session import make_engine, make_sessionmaker, run_migrations
from insightforge.demo.generate import write
from insightforge.ingest.service import ingest_file
from insightforge.relationships import create_relationship

DESCRIPTIONS = {
    "customers": "SYNTHETIC demo — Lumen Commerce customers (fictional).",
    "subscriptions": "SYNTHETIC demo — one subscription per customer; churned is 0/1.",
    "orders": "SYNTHETIC demo — order lines with discounts and refunds.",
    "products": "SYNTHETIC demo — product catalogue.",
}
RELATIONSHIPS = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("orders", "product_id", "products", "product_id"),
    ("subscriptions", "customer_id", "customers", "customer_id"),
]


def seed(data_dir: Path | None = None, settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    engine = make_engine(settings.metadata_db_path)
    run_migrations(engine)
    db = make_sessionmaker(engine)()
    src = data_dir or settings.data_dir / "demo-src"
    created = []
    for path in write(src):
        name = path.stem
        if db.scalars(select(Dataset).where(Dataset.table_name == name)).first():
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        (ds,) = ingest_file(
            db,
            settings,
            upload_path=path,
            filename=path.name,
            sha256=sha,
            display_name=name,
            is_demo=True,
        )
        ds.description = DESCRIPTIONS[name]
        db.commit()
        created.append(name)
    by_name = {d.table_name: d for d in db.scalars(select(Dataset))}
    for lt, lc, rt, rc in RELATIONSHIPS:
        if lt in by_name and rt in by_name:
            create_relationship(db, settings, by_name[lt], lc, by_name[rt], rc, exist_ok=True)
    db.close()
    engine.dispose()
    return created


if __name__ == "__main__":
    print("seeded:", seed() or "(already present)", file=sys.stderr)
