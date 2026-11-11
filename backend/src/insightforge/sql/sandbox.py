"""Run untrusted SQL in a separate, resource-limited, network-less OS process.

Isolation layers (outermost first):

1. **OS sandbox** — on macOS, ``sandbox-exec`` with a profile that denies all network
   access, denies file writes, and only allows reading the Python runtime, this package
   and the specific Parquet files of the query. On Linux, ``bwrap`` (bubblewrap) is used
   when installed (``--unshare-all`` incl. network, read-only binds). If neither is
   available the isolation level is reported as ``rlimits`` and documented as weaker.
2. **Resource limits** — CPU seconds, file size 0 (no writes), open files, address space
   where the kernel enforces it (Linux), plus a wall-clock timeout that kills the process.
3. **Clean process** — ``python -I`` (isolated mode), empty environment, empty temp cwd.
4. **Locked DuckDB** — in-memory, explicit views only, ``allowed_paths``, external access
   disabled, extension autoload/install disabled, configuration locked, memory limit.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import insightforge

log = logging.getLogger("insightforge.sandbox")


@dataclass(frozen=True)
class SandboxLimits:
    timeout_seconds: float = 10.0
    memory_mb: int = 1024
    max_rows: int = 10_000
    threads: int = 2


@dataclass
class SandboxResult:
    ok: bool
    columns: list[str]
    types: list[str]
    rows: list[list[Any]]
    truncated: bool
    elapsed_ms: float
    isolation: str
    error: str | None = None
    error_type: str | None = None


def _package_root() -> Path:
    return Path(insightforge.__file__).resolve().parent.parent


def _interpreter_link_dirs() -> set[Path]:
    """Directories named along the interpreter's symlink chain, *unresolved*.

    Tools like uv point ``.venv/bin/python`` at a version-alias directory that is itself a
    symlink (``cpython-3.13-linux-x86_64-gnu -> cpython-3.13.9-...``). A bind-mount
    sandbox must expose those link paths, not only the fully resolved target.
    """
    dirs: set[Path] = set()
    current = Path(sys.executable)
    for _ in range(10):
        if not current.is_symlink():
            break
        target = Path(os.readlink(current))
        if not target.is_absolute():
            target = current.parent / target
        dirs.add(target.parent.parent)  # <python home>/bin/python -> <python home>
        current = target
    return dirs


def _read_roots(files: list[Path]) -> list[Path]:
    roots = _interpreter_link_dirs() | {
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
        Path(sys.executable).resolve().parent.parent,
        Path(sysconfig.get_paths()["purelib"]).resolve(),
        Path(sysconfig.get_paths()["platlib"]).resolve(),
        _package_root(),
    }
    return sorted(roots) + [f.resolve() for f in files]


def _sbpl_quote(p: Path) -> str:
    return '"' + str(p).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _macos_profile(read_paths: list[Path]) -> str:
    """SBPL profile: no network, no writes, and no reads of user/temp areas (/Users, /Volumes,
    per-user temp dirs) except the Python runtime, this package and the query's Parquet
    files. Later rules take precedence."""
    allows = "\n".join(
        f"(allow file-read* ({'subpath' if p.is_dir() else 'literal'} {_sbpl_quote(p)}))"
        for p in read_paths
    )
    return f"""(version 1)
(deny default)
(allow process-exec* process-fork)
(allow signal (target self))
(allow sysctl-read mach-lookup ipc-posix-shm*)
(allow file-read*)
(deny file-read* (subpath "/Users") (subpath "/Volumes") (subpath "/private/var/folders")
  (subpath "/private/tmp") (subpath "/private/var/root") (subpath "/private/var/db"))
{allows}
(allow file-read-metadata)
(allow file-write-data (literal "/dev/null"))
(deny file-write* (require-not (literal "/dev/null")))
(deny network*)
"""


def _preexec(limits: SandboxLimits) -> None:  # runs in the child before exec
    import resource

    cpu = max(1, int(limits.timeout_seconds) + 1)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if platform.system() == "Linux":
        # Address-space cap: DuckDB limit + headroom for the interpreter and libraries.
        cap = (limits.memory_mb + 768) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    os.setsid()


@functools.cache
def isolation_level() -> str:
    """Strongest isolation that actually *works* here (probed once, not just detected)."""
    if platform.system() == "Darwin" and shutil.which("sandbox-exec"):
        probe = ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)", "/usr/bin/true"]
    elif platform.system() == "Linux" and shutil.which("bwrap"):
        probe = ["bwrap", "--unshare-all", "--ro-bind", "/", "/", "/bin/true"]
    else:
        return "rlimits"
    try:
        ok = subprocess.run(probe, capture_output=True, timeout=10, check=False).returncode == 0  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    if not ok:
        return "rlimits"
    return "sandbox-exec" if probe[0] == "sandbox-exec" else "bwrap"


def wrapper(level: str, read_paths: list[Path]) -> list[str]:
    """argv prefix that runs a command inside the given isolation level."""
    if level == "sandbox-exec":
        return ["sandbox-exec", "-p", _macos_profile(read_paths)]
    if level == "bwrap":
        cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--proc", "/proc"]
        cmd += ["--dev", "/dev", "--tmpfs", "/tmp", "--chdir", "/"]  # noqa: S108 - inside sandbox
        for ro in ("/usr", "/lib", "/lib64", "/bin", "/etc/ld.so.cache", "/etc/localtime"):
            if Path(ro).exists():
                cmd += ["--ro-bind", ro, ro]
        for p in read_paths:
            cmd += ["--ro-bind", str(p), str(p)]
        # Make bwrap's own root read-only too (only the private /tmp tmpfs stays writable).
        cmd += ["--remount-ro", "/"]
        return cmd
    return []


def _command(level: str, read_paths: list[Path]) -> list[str]:
    return [*wrapper(level, read_paths), sys.executable, "-I", "-m", "insightforge.sql.worker"]


def run_sandboxed(
    sql: str, views: Mapping[str, Path], limits: SandboxLimits, *, level: str | None = None
) -> SandboxResult:
    level = level or isolation_level()
    files = [p.resolve() for p in views.values()]
    request = {
        "sql": sql,
        "views": {k: str(v) for k, v in zip(views.keys(), files, strict=True)},
        "max_rows": limits.max_rows,
        "memory_mb": limits.memory_mb,
        "threads": limits.threads,
    }
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    # cwd "/" is readable inside every profile and holds nothing writable or private.
    workdir = "/"
    # -I ignores PYTHONPATH; the package is importable via the venv's site-packages.
    cmd = _command(level, _read_roots(files))
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd,
            input=json.dumps(request).encode(),
            capture_output=True,
            timeout=limits.timeout_seconds,
            cwd=workdir,
            env=env,
            preexec_fn=lambda: _preexec(limits),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failure(level, "Query exceeded the time limit", "Timeout")
    if proc.returncode != 0 and not proc.stdout:
        # stderr can contain paths; it goes to the server log only, never to the client.
        log.warning(
            "sandbox_worker_failed",
            extra={
                "isolation": level,
                "returncode": proc.returncode,
                "stderr": proc.stderr.decode(errors="replace")[-2000:],
            },
        )
        reason = "Query process was terminated (resource limit)"
        if proc.returncode in (-24, 152):  # SIGXCPU
            reason = "Query exceeded the CPU time limit"
        return _failure(level, reason, "ResourceLimit")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _failure(level, "Query worker returned an invalid response", "WorkerError")
    if not data.get("ok"):
        return _failure(level, data.get("error", "Query failed"), data.get("error_type"))
    return SandboxResult(
        ok=True,
        columns=data["columns"],
        types=data["types"],
        rows=data["rows"],
        truncated=data["truncated"],
        elapsed_ms=data["elapsed_ms"],
        isolation=level,
    )


def _failure(level: str, error: str, error_type: str | None) -> SandboxResult:
    return SandboxResult(
        ok=False,
        columns=[],
        types=[],
        rows=[],
        truncated=False,
        elapsed_ms=0.0,
        isolation=level,
        error=error,
        error_type=error_type,
    )
