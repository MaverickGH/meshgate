"""Child processes of a generation run: Blender, TripoSR, AI CLIs. Each gets its own process group, and a SIGTERM to
the run (Studio's Cancel, a closing app) stops them all instead of leaving Blender working in the background."""

from __future__ import annotations

import os
import signal
import subprocess
import sys

ACTIVE: set = set()


def popen(cmd, **kw) -> subprocess.Popen:
    kw.setdefault("start_new_session" if os.name != "nt" else "creationflags",
                  True if os.name != "nt" else subprocess.CREATE_NEW_PROCESS_GROUP)
    proc = subprocess.Popen(cmd, **kw)
    ACTIVE.add(proc)
    return proc


def stop_tree(proc) -> None:
    """Stop a process and everything it started."""
    ACTIVE.discard(proc)
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def stop_all() -> None:
    for proc in list(ACTIVE):
        stop_tree(proc)


def run(cmd, *, timeout: float | None = None, input: str | None = None, **kw):
    """subprocess.run with text output, a process group and a clean stop on timeout (raises TimeoutExpired)."""
    proc = popen(cmd, stdin=subprocess.PIPE if input is not None else None, stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", **kw)
    try:
        out, err = proc.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_tree(proc)
        raise
    finally:
        ACTIVE.discard(proc)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def install_handlers() -> None:
    """On SIGTERM/SIGINT (or Ctrl+Break on Windows): stop every child tree, then exit."""
    def handler(signum, _frame):
        stop_all()
        sys.exit(128 + int(signum))
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), handler)
            except (ValueError, OSError):   # not the main thread
                pass
