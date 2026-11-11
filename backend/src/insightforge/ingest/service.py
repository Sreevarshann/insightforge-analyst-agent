"""Ingestion orchestration: stream to disk, detect, parse, normalize, store as Parquet."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path, PurePath
from typing import BinaryIO

import duckdb
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from insightforge.config import Settings
from insightforge.db.models import Dataset, DatasetVersion
from insightforge.ingest.formats import IngestError, ParsedTable, detect_format, parse
from insightforge.ingest.normalize import normalize_columns, to_identifier, unique_identifier


def safe_filename(name: str | None) -> str:
    base = PurePath((name or "").replace("\\", "/")).name.strip()
    if not base or base in {".", ".."}:
        raise IngestError("Missing filename")
    return base[:200]


def spool_upload(src: BinaryIO, settings: Settings, max_bytes: int) -> tuple[Path, str, int]:
    """Write an upload to a private temp file with a hard size cap. Returns (path, sha256, size)."""
    tmp_dir = settings.data_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=tmp_dir, prefix="upload-")
    path = Path(name)
    digest, size = hashlib.sha256(), 0
    try:
        with open(fd, "wb") as fh:
            while chunk := src.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise IngestError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit")
                digest.update(chunk)
                fh.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if size == 0:
        path.unlink(missing_ok=True)
        raise IngestError("File is empty")
    return path, digest.hexdigest(), size


def describe_schema(parquet_path: Path) -> list[dict[str, object]]:
    con = duckdb.connect()
    try:
        rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet_path)]).fetchall()
    finally:
        con.close()
    return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES"} for r in rows]


def _store(settings: Settings, dataset: Dataset, version: int, parsed: ParsedTable) -> Path:
    rel = Path(dataset.id) / f"v{version}.parquet"
    dest = settings.datasets_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(normalize_columns(parsed.table), dest, compression="zstd")
    return rel


def ingest_file(
    db: Session,
    settings: Settings,
    *,
    upload_path: Path,
    filename: str,
    sha256: str,
    display_name: str | None = None,
    is_demo: bool = False,
) -> list[Dataset]:
    """Create one new dataset per table/sheet in the upload."""
    fmt = detect_format(filename, upload_path)
    stem = Path(filename).stem
    parsed_tables = parse(fmt, upload_path, stem)
    taken = set(db.scalars(select(Dataset.table_name)))
    created: list[Dataset] = []
    for parsed in parsed_tables:
        label = display_name or stem
        if len(parsed_tables) > 1:
            label = f"{label} · {parsed.name}"
        table_name = unique_identifier(to_identifier(label), taken)
        taken.add(table_name)
        ds = Dataset(table_name=table_name, display_name=label, is_demo=is_demo)
        db.add(ds)
        db.flush()  # assigns id
        ds.versions.append(_make_version(settings, ds, 1, fmt, filename, sha256, parsed))
        created.append(ds)
    db.commit()
    return created


def add_version(
    db: Session,
    settings: Settings,
    dataset: Dataset,
    *,
    upload_path: Path,
    filename: str,
    sha256: str,
) -> DatasetVersion:
    fmt = detect_format(filename, upload_path)
    parsed = parse(fmt, upload_path, Path(filename).stem)
    if len(parsed) != 1:
        raise IngestError("A new version must contain exactly one table")
    current = dataset.current
    if current is not None and current.sha256 == sha256:
        raise IngestError("This file is identical to the current version")
    n = (current.version if current else 0) + 1
    ver = _make_version(settings, dataset, n, fmt, filename, sha256, parsed[0])
    dataset.versions.append(ver)
    db.commit()
    return ver


def _make_version(
    settings: Settings,
    ds: Dataset,
    n: int,
    fmt: str,
    filename: str,
    sha256: str,
    parsed: ParsedTable,
) -> DatasetVersion:
    rel = _store(settings, ds, n, parsed)
    schema = describe_schema(settings.datasets_dir / rel)
    return DatasetVersion(
        version=n,
        source_format=fmt,
        source_name=filename,
        sha256=sha256,
        storage_path=str(rel),
        row_count=parsed.table.num_rows,
        column_count=len(schema),
        schema_json=schema,
    )


def delete_dataset(db: Session, settings: Settings, dataset: Dataset) -> None:
    directory = settings.datasets_dir / dataset.id
    db.delete(dataset)
    db.commit()
    # dataset.id is a server-generated hex uuid; resolve to be sure we stay inside datasets_dir
    root = settings.datasets_dir.resolve()
    target = directory.resolve()
    if target.parent == root and target.is_dir():
        shutil.rmtree(target)
