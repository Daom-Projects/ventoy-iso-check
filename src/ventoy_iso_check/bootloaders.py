"""Inventario y comprobación de herramientas en Bootloaders/ (no solo Ventoy).

Detecta:
  - Ventoy (carpeta ventoy-*/ventoy/version)
  - Rufus portable/setup (rufus-*.exe)
  - balenaEtcher (Setup.exe / zip / dmg)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from ventoy_iso_check.ventoy_info import (
    USER_AGENT,
    _ver_tuple,
    check_ventoy,
)

log = logging.getLogger(__name__)


@dataclass
class ToolStatus:
    id: str
    label: str
    local_version: str | None = None
    local_path: str | None = None
    latest_version: str | None = None
    latest_url: str | None = None
    status: str = "UNKNOWN"  # OK | OUTDATED | UNKNOWN | NOT_FOUND | ERROR
    note: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "local_version": self.local_version,
            "local_path": self.local_path,
            "latest_version": self.latest_version,
            "latest_url": self.latest_url,
            "status": self.status,
            "note": self.note,
        }


def _cmp_status(local: str | None, latest: str | None) -> str:
    if not local:
        return "NOT_FOUND"
    if not latest:
        return "UNKNOWN"
    try:
        if _ver_tuple(local) < _ver_tuple(latest):
            return "OUTDATED"
        return "OK"
    except Exception:
        if local == latest:
            return "OK"
        return "UNKNOWN"


def _find_rufus(boot: Path) -> ToolStatus:
    st = ToolStatus(
        id="rufus",
        label="Rufus",
        latest_url="https://rufus.ie/",
    )
    if not boot.is_dir():
        st.status = "NOT_FOUND"
        st.note = "No hay carpeta Bootloaders/"
        return st

    candidates = sorted(boot.glob("rufus*.exe"), key=lambda p: p.name.lower())
    if not candidates:
        # also one level deep
        candidates = sorted(boot.glob("**/rufus*.exe"), key=lambda p: p.name.lower())
    if not candidates:
        st.status = "NOT_FOUND"
        st.note = "No se encontró rufus*.exe"
        return st

    best = candidates[-1]
    m = re.search(r"rufus[-_]?(\d+(?:\.\d+)*)", best.name, flags=re.I)
    st.local_version = m.group(1) if m else None
    st.local_path = str(best)
    portable = "p" in best.stem.lower() and best.stem.lower().endswith("p")
    st.note = "Portable" if portable or "p.exe" in best.name.lower() else "Setup/standard"
    return st


def _find_etcher(boot: Path) -> ToolStatus:
    st = ToolStatus(
        id="balena-etcher",
        label="balenaEtcher",
        latest_url="https://github.com/balena-io/etcher/releases",
    )
    if not boot.is_dir():
        st.status = "NOT_FOUND"
        return st

    patterns = (
        "balenaEtcher*",
        "balena-etcher*",
        "Etcher*",
    )
    files: list[Path] = []
    for pat in patterns:
        files.extend(boot.glob(pat))
    files = [f for f in files if f.is_file()]
    if not files:
        st.status = "NOT_FOUND"
        st.note = "No se encontró balenaEtcher*"
        return st

    # Prefer Windows Setup, then zip, then dmg
    def rank(p: Path) -> tuple[int, str]:
        n = p.name.lower()
        if n.endswith(".setup.exe") or "setup.exe" in n:
            return (0, n)
        if n.endswith(".exe"):
            return (1, n)
        if n.endswith(".zip"):
            return (2, n)
        if n.endswith(".dmg"):
            return (3, n)
        return (9, n)

    best = sorted(files, key=rank)[0]
    m = re.search(r"(\d+\.\d+\.\d+)", best.name)
    st.local_version = m.group(1) if m else None
    st.local_path = str(best)
    kinds = sorted({p.suffix.lower().lstrip(".") or p.name for p in files})
    st.note = f"Archivos: {', '.join(p.name for p in sorted(files, key=lambda x: x.name)[:5])}"
    if len(files) > 5:
        st.note += f" (+{len(files) - 5})"
    _ = kinds
    return st


def fetch_latest_rufus() -> tuple[str | None, str | None, str | None]:
    """Return (version, url, error)."""
    page = "https://rufus.ie/"
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=25.0,
        ) as client:
            # GitHub releases API is cleaner
            r = client.get(
                "https://api.github.com/repos/pbatard/rufus/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            r.raise_for_status()
            data = r.json()
            tag = (data.get("tag_name") or "").lstrip("v")
            url = data.get("html_url") or page
            return tag or None, url, None
    except Exception as e:
        log.warning("Rufus latest: %s", e)
        return None, page, str(e)


def fetch_latest_etcher() -> tuple[str | None, str | None, str | None]:
    page = "https://github.com/balena-io/etcher/releases"
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
            follow_redirects=True,
            timeout=25.0,
        ) as client:
            r = client.get(
                "https://api.github.com/repos/balena-io/etcher/releases/latest"
            )
            r.raise_for_status()
            data = r.json()
            tag = (data.get("tag_name") or "").lstrip("v")
            url = data.get("html_url") or page
            return tag or None, url, None
    except Exception as e:
        log.warning("Etcher latest: %s", e)
        return None, page, str(e)


def check_bootloaders(root: Path, *, online: bool = True) -> list[ToolStatus]:
    """Scan ROOT/Bootloaders (or ROOT) for known tools and optionally compare upstream."""
    root = root.resolve()
    boot = root / "Bootloaders"
    if not boot.is_dir():
        boot = root

    results: list[ToolStatus] = []

    # Ventoy (reuse existing logic)
    v = check_ventoy(root, online=online)
    results.append(
        ToolStatus(
            id="ventoy",
            label="Ventoy",
            local_version=v.local_version,
            local_path=v.local_path,
            latest_version=v.latest_version,
            latest_url=v.latest_url,
            status=v.status,
            note=v.note,
        )
    )

    rufus = _find_rufus(boot)
    if online and rufus.local_version:
        latest, url, err = fetch_latest_rufus()
        rufus.latest_version = latest
        rufus.latest_url = url
        if err and not latest:
            rufus.status = "ERROR"
            rufus.note = (rufus.note or "") + f" | {err}"
        else:
            rufus.status = _cmp_status(rufus.local_version, latest)
    elif rufus.local_version:
        rufus.status = "UNKNOWN"
        rufus.note = (rufus.note or "") + " | offline"
    results.append(rufus)

    etcher = _find_etcher(boot)
    if online and etcher.local_version:
        latest, url, err = fetch_latest_etcher()
        etcher.latest_version = latest
        etcher.latest_url = url
        if err and not latest:
            etcher.status = "ERROR"
            etcher.note = (etcher.note or "") + f" | {err}"
        else:
            etcher.status = _cmp_status(etcher.local_version, latest)
    elif etcher.local_version:
        etcher.status = "UNKNOWN"
        etcher.note = (etcher.note or "") + " | offline"
    results.append(etcher)

    return results


def format_bootloaders_console(tools: list[ToolStatus]) -> str:
    lines = ["=== Bootloaders / herramientas ==="]
    for t in tools:
        lines.append(f"  [{t.status:9}] {t.label}")
        lines.append(f"             local:  {t.local_version or '-'}  ({t.local_path or '-'})")
        lines.append(f"             latest: {t.latest_version or '-'}")
        if t.latest_url:
            lines.append(f"             url:    {t.latest_url}")
        if t.note:
            lines.append(f"             note:   {t.note}")
    return "\n".join(lines)
