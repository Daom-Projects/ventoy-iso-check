from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "ventoy-iso-check/ventoy-check (+https://github.com/Daom-Projects/ventoy-iso-check)"
GITHUB_LATEST = "https://api.github.com/repos/ventoy/Ventoy/releases/latest"
VENTOY_DOWNLOAD = "https://www.ventoy.net/en/download.html"


@dataclass
class VentoyStatus:
    local_version: str | None = None
    local_path: str | None = None
    latest_version: str | None = None
    latest_url: str | None = None
    status: str = "UNKNOWN"  # OK | OUTDATED | UNKNOWN | ERROR | NOT_FOUND
    note: str | None = None

    def to_dict(self) -> dict:
        return {
            "local_version": self.local_version,
            "local_path": self.local_path,
            "latest_version": self.latest_version,
            "latest_url": self.latest_url,
            "status": self.status,
            "note": self.note,
        }


def _normalize_ver(v: str) -> str:
    v = v.strip().lstrip("vV")
    return v


def _find_local_version(root: Path) -> tuple[str | None, Path | None]:
    """Locate Ventoy version file under a Ventoy data partition."""
    root = root.resolve()
    candidates: list[Path] = []

    # Author layout: Bootloaders/ventoy-1.1.10/ventoy/version
    bootloaders = root / "Bootloaders"
    if bootloaders.is_dir():
        for p in sorted(bootloaders.glob("ventoy-*/ventoy/version")):
            candidates.append(p)

    # Classic: ventoy/version at partition root
    classic = root / "ventoy" / "version"
    if classic.is_file():
        candidates.append(classic)

    # Loose search (depth limited)
    if not candidates:
        try:
            for dirpath, dirnames, filenames in root.walk(on_error=lambda _e: None):
                try:
                    rel = dirpath.relative_to(root)
                except ValueError:
                    continue
                if len(rel.parts) > 3:
                    dirnames.clear()
                    continue
                if "version" in filenames and dirpath.name == "ventoy":
                    candidates.append(dirpath / "version")
        except OSError:
            pass

    # Prefer highest version if multiple installer copies
    best_ver: str | None = None
    best_path: Path | None = None
    for c in candidates:
        try:
            text = c.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not text:
            continue
        # first line often just "1.1.10"
        ver = _normalize_ver(text.splitlines()[0])
        if not re.match(r"^\d+\.\d+", ver):
            # folder name ventoy-1.1.10
            m = re.search(r"ventoy-(\d+\.\d+(?:\.\d+)*)", str(c), flags=re.I)
            if m:
                ver = m.group(1)
            else:
                continue
        if best_ver is None or _ver_tuple(ver) > _ver_tuple(best_ver):
            best_ver = ver
            best_path = c
    return best_ver, best_path


def _ver_tuple(v: str) -> tuple[int, ...]:
    parts = []
    for p in _normalize_ver(v).split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def fetch_latest_ventoy() -> tuple[str | None, str | None, str | None]:
    """Return (version, html_url, error)."""
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
            follow_redirects=True,
            timeout=25.0,
        ) as client:
            r = client.get(GITHUB_LATEST)
            r.raise_for_status()
            data = r.json()
            tag = _normalize_ver(data.get("tag_name") or "")
            url = data.get("html_url") or VENTOY_DOWNLOAD
            if not tag:
                return None, url, "GitHub latest sin tag_name"
            return tag, url, None
    except Exception as e:
        log.warning("No se pudo consultar Ventoy latest: %s", e)
        return None, VENTOY_DOWNLOAD, str(e)


def check_ventoy(root: Path, *, online: bool = True) -> VentoyStatus:
    local, path = _find_local_version(root)
    st = VentoyStatus(
        local_version=local,
        local_path=str(path) if path else None,
    )
    if local is None:
        st.status = "NOT_FOUND"
        st.note = (
            "No se encontró ventoy/version (¿Bootloaders/ventoy-*/ventoy/version?)."
        )
        if online:
            latest, url, err = fetch_latest_ventoy()
            st.latest_version = latest
            st.latest_url = url
            if err and not latest:
                st.note = f"{st.note} Upstream: {err}"
        return st

    if not online:
        st.status = "UNKNOWN"
        st.note = "Offline: solo versión local"
        return st

    latest, url, err = fetch_latest_ventoy()
    st.latest_version = latest
    st.latest_url = url
    if err and not latest:
        st.status = "ERROR"
        st.note = err
        return st
    if latest is None:
        st.status = "UNKNOWN"
        st.note = "No se pudo determinar la última versión de Ventoy"
        return st

    if _ver_tuple(local) < _ver_tuple(latest):
        st.status = "OUTDATED"
        st.note = f"Actualizar Ventoy {local} → {latest} (bootloader, no las ISOs)"
    elif _ver_tuple(local) == _ver_tuple(latest):
        st.status = "OK"
        st.note = "Bootloader Ventoy al día"
    else:
        st.status = "OK"
        st.note = f"Local {local} ≥ upstream {latest}"
    return st


def format_ventoy_console(st: VentoyStatus) -> str:
    lines = [
        "=== Ventoy bootloader ===",
        f"  local:  {st.local_version or '—'}  ({st.local_path or 'no path'})",
        f"  latest: {st.latest_version or '—'}",
        f"  status: {st.status}",
    ]
    if st.latest_url:
        lines.append(f"  url:    {st.latest_url}")
    if st.note:
        lines.append(f"  note:   {st.note}")
    return "\n".join(lines)


def format_ventoy_html(st: VentoyStatus) -> str:
    import html as html_mod

    rows = [
        f"<p><strong>Local:</strong> {html_mod.escape(st.local_version or '—')} "
        f"<code>{html_mod.escape(st.local_path or '')}</code></p>",
        f"<p><strong>Latest:</strong> {html_mod.escape(st.latest_version or '—')}</p>",
        f"<p><strong>Status:</strong> {html_mod.escape(st.status)}</p>",
    ]
    if st.latest_url:
        rows.append(
            f'<p><a href="{html_mod.escape(st.latest_url)}">Descargas Ventoy</a></p>'
        )
    if st.note:
        rows.append(f"<p>{html_mod.escape(st.note)}</p>")
    return "\n".join(rows)
