"""OS-level sandbox tests. These run real subprocesses; they do not mock isolation."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from insightforge.sql import sandbox as sb
from insightforge.sql.sandbox import SandboxLimits, run_sandboxed

pytestmark = pytest.mark.sandbox


@pytest.fixture
def parquet(tmp_path: Path) -> Path:
    p = tmp_path / "t.parquet"
    pq.write_table(pa.table({"x": list(range(1000)), "g": ["a", "b"] * 500}), p)
    return p


def test_query_runs_in_separate_process(parquet: Path) -> None:
    r = run_sandboxed(
        "SELECT g, sum(x) s FROM t GROUP BY g ORDER BY g", {"t": parquet}, SandboxLimits()
    )
    assert r.ok, r.error
    assert r.rows == [["a", 249500], ["b", 250000]]
    assert r.isolation == sb.isolation_level()


def test_row_cap_truncates(parquet: Path) -> None:
    r = run_sandboxed("SELECT x FROM t", {"t": parquet}, SandboxLimits(max_rows=10))
    assert r.ok and len(r.rows) == 10 and r.truncated


def test_wall_clock_timeout_kills_runaway_query(parquet: Path) -> None:
    # Bypasses the validator on purpose: proves the sandbox itself bounds execution time.
    r = run_sandboxed(
        "SELECT count(*) FROM range(1000000000000) a",
        {"t": parquet},
        SandboxLimits(timeout_seconds=1.5),
    )
    assert not r.ok and r.error_type in {"Timeout", "ResourceLimit"}


def test_duckdb_layer_blocks_file_reads_even_without_validator(
    parquet: Path, tmp_path: Path
) -> None:
    secret = tmp_path / "secret.csv"
    secret.write_text("k\nhunter2\n")
    r = run_sandboxed(f"SELECT * FROM read_csv('{secret}')", {"t": parquet}, SandboxLimits())
    assert not r.ok
    assert "hunter2" not in (r.error or "")


def test_memory_limit_surfaces_as_error(parquet: Path) -> None:
    r = run_sandboxed(
        "SELECT list(x) FROM (SELECT x FROM range(200000000) r(x))",
        {"t": parquet},
        SandboxLimits(memory_mb=64, timeout_seconds=20),
    )
    assert not r.ok


def _run_python_in_profile(code: str, read_paths: list[Path]) -> subprocess.CompletedProcess[bytes]:
    profile = sb._macos_profile(sb._read_roots(read_paths))
    return subprocess.run(
        ["sandbox-exec", "-p", profile, sys.executable, "-I", "-c", code],
        capture_output=True,
        timeout=30,
        check=False,
        cwd="/",
    )


macos_only = pytest.mark.skipif(
    sb.isolation_level() != "sandbox-exec", reason="macOS sandbox-exec not available"
)


@macos_only
def test_os_sandbox_blocks_network(parquet: Path) -> None:
    code = (
        "import socket\n"
        "try:\n socket.create_connection(('1.1.1.1', 53), timeout=3); print('CONNECTED')\n"
        "except OSError as e: print('BLOCKED', e.errno)\n"
    )
    out = _run_python_in_profile(code, [parquet]).stdout.decode()
    assert "BLOCKED" in out and "CONNECTED" not in out


@macos_only
def test_os_sandbox_blocks_reading_home_files(parquet: Path, tmp_path: Path) -> None:
    secret = Path.home() / ".insightforge_sandbox_probe"
    secret.write_text("private")
    try:
        code = f"open({str(secret)!r}).read(); print('READ')"
        res = _run_python_in_profile(code, [parquet])
        assert b"READ" not in res.stdout and res.returncode != 0
    finally:
        secret.unlink()


@macos_only
def test_os_sandbox_allows_only_registered_dataset(parquet: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.txt"
    other.write_text("nope")
    code = f"print(len(open({str(parquet)!r}, 'rb').read()) > 0); open({str(other)!r}).read()"
    res = _run_python_in_profile(code, [parquet])
    assert res.stdout.startswith(b"True") and res.returncode != 0


@macos_only
def test_os_sandbox_blocks_writes(parquet: Path) -> None:
    code = "open('/tmp/insightforge_probe.txt', 'w').write('x'); print('WROTE')"
    res = _run_python_in_profile(code, [parquet])
    assert b"WROTE" not in res.stdout
    assert not Path("/tmp/insightforge_probe.txt").exists()


@pytest.mark.skipif(platform.system() != "Linux", reason="RLIMIT_AS enforced on Linux only")
def test_linux_address_space_limit_applied(parquet: Path) -> None:
    r = run_sandboxed("SELECT 1 FROM t LIMIT 1", {"t": parquet}, SandboxLimits(memory_mb=256))
    assert r.ok
