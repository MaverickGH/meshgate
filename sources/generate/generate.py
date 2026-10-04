"""MeshGate native entry point. See LICENSE."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from native_loader import load as _load
_native = _load('sources/generate/generate.py', globals())
if __name__ == "__main__" and hasattr(_native, "main"):
    raise SystemExit(_native.main())
