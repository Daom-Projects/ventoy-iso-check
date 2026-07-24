from __future__ import annotations

import os
from pathlib import Path

# Preferencia de montaje portable (Docker / docs) y fallbacks habituales.
_CANDIDATES = (
    "VENTOY_ROOT",
    "VENTOY_PATH",
)


def default_ventoy_root() -> Path:
    """Raíz del volumen Ventoy.

    Orden:
    1. ``VENTOY_ROOT`` / ``VENTOY_PATH``
    2. ``/ventoy`` (convención Docker y docs multiplataforma)
    3. ``/mnt/e`` (WSL Windows letra E:)
    4. directorio actual
    """
    for key in _CANDIDATES:
        raw = os.environ.get(key)
        if raw:
            return Path(raw).expanduser()

    for candidate in (Path("/ventoy"), Path("/mnt/e")):
        if candidate.is_dir():
            return candidate

    return Path.cwd()


def project_root() -> Path:
    """Raíz del proyecto (catalog.yaml, sisou.toml)."""
    # src/ventoy_iso_check/paths.py → parents[2] = project root when installed editable
    # When installed as wheel, data files may live next to package or site-packages parent.
    here = Path(__file__).resolve()
    # Prefer parent of package if catalog.yaml is two levels up (dev tree)
    for parent in (here.parents[2], here.parents[1], Path.cwd()):
        if (parent / "catalog.yaml").is_file() or (parent / "sisou.toml").is_file():
            return parent
    return here.parents[2]
