"""Format detection and parsing of untrusted uploads into Arrow tables.

Every parser produces one or more named ``pyarrow.Table`` objects. Nothing in an uploaded
file is ever executed: Excel formulas are read as cached values, SQLite files are opened
read-only/immutable, and XLSX archives are checked for decompression bombs first.
"""

from __future__ import annotations

import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".tab": "tsv",
    ".xlsx": "xlsx",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".db": "sqlite",
}

_MAGIC = {
    "xlsx": b"PK\x03\x04",
    "parquet": b"PAR1",
    "sqlite": b"SQLite format 3\x00",
}

MAX_XLSX_UNCOMPRESSED = 400 * 1024 * 1024
MAX_SHEETS_OR_TABLES = 50
MAX_COLUMNS = 2_000


class IngestError(ValueError):
    """A user-facing ingestion failure. Messages never include file contents."""


@dataclass(frozen=True)
class ParsedTable:
    name: str  # sheet / table name, or the file stem
    table: pa.Table


def detect_format(filename: str, path: Path) -> str:
    ext = Path(filename).suffix.lower()
    fmt = SUPPORTED_EXTENSIONS.get(ext)
    if fmt is None:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise IngestError(f"Unsupported file type '{ext or '(none)'}'. Allowed: {allowed}")
    magic = _MAGIC.get(fmt)
    with path.open("rb") as fh:
        head = fh.read(16)
    if magic is not None and not head.startswith(magic):
        raise IngestError(f"File content does not match the {fmt} format")
    if fmt in {"csv", "tsv"} and b"\x00" in head:
        raise IngestError("Text file appears to be binary")
    if fmt == "parquet":
        with path.open("rb") as fh:
            fh.seek(-4, 2)
            if fh.read(4) != b"PAR1":
                raise IngestError("Parquet file is truncated")
    return fmt


def parse(fmt: str, path: Path, stem: str) -> list[ParsedTable]:
    try:
        match fmt:
            case "csv" | "tsv":
                tables = [ParsedTable(stem, _read_delimited(path, "\t" if fmt == "tsv" else None))]
            case "parquet":
                tables = [ParsedTable(stem, pq.read_table(path))]
            case "xlsx":
                tables = _read_xlsx(path)
            case "sqlite":
                tables = _read_sqlite(path)
            case _:
                raise IngestError(f"Unsupported format {fmt}")
    except IngestError:
        raise
    except Exception as exc:  # parser-specific errors -> generic, content-free message
        raise IngestError(f"Could not parse {fmt} file ({type(exc).__name__})") from exc
    tables = [t for t in tables if t.table.num_columns > 0]
    if not tables:
        raise IngestError("No tabular data found in file")
    for t in tables:
        if t.table.num_columns > MAX_COLUMNS:
            raise IngestError(f"Too many columns ({t.table.num_columns} > {MAX_COLUMNS})")
    return tables


def _read_delimited(path: Path, delimiter: str | None) -> pa.Table:
    con = duckdb.connect(config={"autoinstall_known_extensions": False})
    try:
        if delimiter is not None:
            rel = con.read_csv(str(path), header=True, sample_size=20_000, sep=delimiter)
        else:
            rel = con.read_csv(str(path), header=True, sample_size=20_000)
        return rel.to_arrow_table()
    finally:
        con.close()


def _read_xlsx(path: Path) -> list[ParsedTable]:
    with zipfile.ZipFile(path) as zf:
        total = sum(info.file_size for info in zf.infolist())
        if total > MAX_XLSX_UNCOMPRESSED:
            raise IngestError("Workbook expands to an unsafe size")
    import pandas as pd  # openpyxl uses defusedxml when installed

    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    if len(sheets) > MAX_SHEETS_OR_TABLES:
        raise IngestError("Workbook has too many sheets")
    out = []
    for name, frame in sheets.items():
        frame = frame.dropna(axis=1, how="all").dropna(axis=0, how="all")
        frame.columns = [str(c) for c in frame.columns]
        # object columns with mixed types -> string, so Arrow conversion is lossless & stable
        for col in frame.columns:
            if frame[col].dtype == object:
                frame[col] = frame[col].map(lambda v: None if pd.isna(v) else str(v))
        out.append(ParsedTable(str(name), pa.Table.from_pandas(frame, preserve_index=False)))
    return out


def _read_sqlite(path: Path) -> list[ParsedTable]:
    uri = f"file:{path}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    try:
        con.execute("PRAGMA trusted_schema=OFF")
        names = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        if len(names) > MAX_SHEETS_OR_TABLES:
            raise IngestError("Database has too many tables")
        out = []
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            cur = con.execute(f"SELECT * FROM {quoted}")  # noqa: S608 - identifier quoted
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            arrays = {c: [r[i] for r in rows] for i, c in enumerate(cols)}
            out.append(ParsedTable(name, pa.table(arrays)))
        return out
    finally:
        con.close()
