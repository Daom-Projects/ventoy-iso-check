"""Consola Rich segura en Windows (cp1252 no soporta → — … ✓)."""

from __future__ import annotations

import os
import sys

from rich.console import Console


def configure_stdio_utf8() -> None:
    """Reconfigurar stdout/stderr a UTF-8 cuando sea posible (Windows)."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        try:
            reconf = getattr(stream, "reconfigure", None)
            if callable(reconf):
                reconf(encoding="utf-8", errors="replace")
        except Exception:
            pass


def make_console(**kwargs) -> Console:
    """Console Rich que no revienta con Unicode en consolas Windows legacy."""
    configure_stdio_utf8()
    # force_terminal=True ayuda con detección; legacy_windows=False evita
    # el renderer Win32 que usa el encoding del sistema (cp1252).
    opts = {
        "force_terminal": kwargs.pop("force_terminal", True),
        "legacy_windows": kwargs.pop("legacy_windows", False),
        "soft_wrap": kwargs.pop("soft_wrap", True),
    }
    opts.update(kwargs)
    try:
        return Console(**opts)
    except Exception:
        return Console(legacy_windows=False, force_terminal=True)
