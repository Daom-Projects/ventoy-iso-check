from __future__ import annotations

import os
from pathlib import Path

# Preferencia de montaje portable (Docker / docs) y fallbacks habituales.
_CANDIDATES = (
    "VENTOY_ROOT",
    "VENTOY_PATH",
)

_MARKER_DIRS = ("Linux", "Herramientas", "Bootloaders", "Windows", "Scripts")


def looks_like_ventoy_root(path: Path) -> bool:
    """True si *path* parece la raíz de un volumen Ventoy (no el repo del tool)."""
    try:
        p = path.resolve()
    except OSError:
        p = path
    if not p.is_dir():
        return False

    # No confundir con solo el clon del proyecto (tiene catalog.yaml + src/)
    is_tool_repo = (p / "catalog.yaml").is_file() and (
        (p / "src" / "ventoy_iso_check").is_dir() or (p / "pyproject.toml").is_file()
    )

    boot = p / "Bootloaders"
    if boot.is_dir():
        try:
            for child in boot.iterdir():
                name = child.name.lower()
                if name.startswith("ventoy") or name.startswith("rufus") or name.startswith(
                    "balena"
                ):
                    return True
                if child.suffix.lower() in (".exe", ".zip", ".dmg", ".tar.gz"):
                    return True
        except OSError:
            pass

    # Carpetas típicas del USB del autor
    hits = 0
    for name in ("Linux", "Herramientas", "Windows", "Bootloaders"):
        if (p / name).is_dir():
            hits += 1
    if hits >= 2 and not is_tool_repo:
        return True
    if hits >= 3:
        return True

    # Alguna ISO en subcarpetas de primer nivel
    for name in ("Linux", "Herramientas", "Windows"):
        d = p / name
        if not d.is_dir():
            continue
        try:
            for child in d.rglob("*"):
                if child.suffix.lower() in (".iso", ".img"):
                    return True
                # limitar profundidad aproximada
                try:
                    if len(child.relative_to(d).parts) > 3:
                        break
                except ValueError:
                    break
        except OSError:
            continue

    return False


def find_ventoy_root_from(start: Path) -> Path | None:
    """Sube desde *start* buscando una raíz Ventoy (p. ej. E:\\ desde E:\\Scripts\\tool)."""
    try:
        cur = start.resolve()
    except OSError:
        cur = start
    # Incluir start y padres (hasta raíz de unidad)
    seen: set[Path] = set()
    for candidate in [cur, *cur.parents]:
        if candidate in seen:
            break
        seen.add(candidate)
        if looks_like_ventoy_root(candidate):
            return candidate
        # Detener en raíz de filesystem (E:\ , / )
        if candidate.parent == candidate:
            break
    return None


def default_ventoy_root() -> Path:
    """Raíz del volumen Ventoy.

    Orden:
    1. ``VENTOY_ROOT`` / ``VENTOY_PATH``
    2. ``/ventoy`` (convención Docker)
    3. ``/mnt/e`` (WSL letra E:)
    4. Detectar subiendo desde el cwd (p. ej. ``E:\\Scripts\\ventoy-iso-check`` → ``E:\\``)
    5. cwd
    """
    for key in _CANDIDATES:
        raw = os.environ.get(key)
        if raw:
            return Path(raw).expanduser()

    for candidate in (Path("/ventoy"), Path("/mnt/e")):
        try:
            if candidate.is_dir() and (
                looks_like_ventoy_root(candidate) or candidate.as_posix() == "/ventoy"
            ):
                return candidate
        except OSError:
            continue

    # Si /mnt/e existe aunque no se vean ISOs (montaje lento), preferirlo a cwd del repo
    mnt_e = Path("/mnt/e")
    if mnt_e.is_dir():
        found = find_ventoy_root_from(mnt_e)
        if found:
            return found

    found = find_ventoy_root_from(Path.cwd())
    if found:
        return found

    return Path.cwd()


def project_root() -> Path:
    """Raíz del proyecto (catalog.yaml, sisou.toml)."""
    here = Path(__file__).resolve()
    for parent in (here.parents[2], here.parents[1], Path.cwd()):
        if (parent / "catalog.yaml").is_file() or (parent / "sisou.toml").is_file():
            return parent
    return here.parents[2]
