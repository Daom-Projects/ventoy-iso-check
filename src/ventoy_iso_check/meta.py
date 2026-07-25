from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ventoy_iso_check import __version__

log = logging.getLogger(__name__)

META_SCHEMA = 1
SIDECAR_SUFFIX = ".meta.json"


@dataclass
class IsoMeta:
    """Sidecar metadata next to an ISO on the Ventoy volume."""

    schema: int = META_SCHEMA
    filename: str = ""
    downloaded_at: str | None = None
    source_url: str | None = None
    sha256: str | None = None
    tool: str = "ventoy-iso-check"
    tool_version: str = field(default_factory=lambda: __version__)
    catalog_id: str | None = None
    local_version: str | None = None
    size: int | None = None
    note: str | None = None

    def downloaded_at_dt(self) -> datetime | None:
        if not self.downloaded_at:
            return None
        try:
            dt = datetime.fromisoformat(self.downloaded_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            return None


def sidecar_path(iso_path: Path) -> Path:
    """foo.iso → foo.iso.meta.json"""
    return Path(str(iso_path) + SIDECAR_SUFFIX)


def load_meta(iso_path: Path) -> IsoMeta | None:
    path = sidecar_path(iso_path)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        return IsoMeta(
            schema=int(raw.get("schema") or META_SCHEMA),
            filename=str(raw.get("filename") or iso_path.name),
            downloaded_at=raw.get("downloaded_at"),
            source_url=raw.get("source_url"),
            sha256=raw.get("sha256"),
            tool=str(raw.get("tool") or "ventoy-iso-check"),
            tool_version=str(raw.get("tool_version") or ""),
            catalog_id=raw.get("catalog_id"),
            local_version=raw.get("local_version"),
            size=raw.get("size"),
            note=raw.get("note"),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
        log.warning("Sidecar ilegible %s: %s", path, e)
        return None


def save_meta(iso_path: Path, meta: IsoMeta) -> Path:
    path = sidecar_path(iso_path)
    if not meta.filename:
        meta.filename = iso_path.name
    meta.schema = META_SCHEMA
    if not meta.tool_version:
        meta.tool_version = __version__
    data = asdict(meta)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def compute_sha256(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(iso_path: Path, expected: str) -> tuple[bool, str]:
    """Return (ok, actual_hex). Does not delete the ISO on mismatch."""
    actual = compute_sha256(iso_path)
    return actual.lower() == expected.lower().strip(), actual


def write_meta_for_iso(
    iso_path: Path,
    *,
    catalog_id: str | None = None,
    local_version: str | None = None,
    source_url: str | None = None,
    downloaded_at: datetime | None = None,
    sha256: str | None = None,
    compute_hash: bool = False,
    note: str | None = None,
    size: int | None = None,
) -> IsoMeta:
    """Create or update sidecar for an ISO."""
    iso_path = iso_path.resolve()
    existing = load_meta(iso_path)
    now = datetime.now(UTC)
    if size is None:
        try:
            size = iso_path.stat().st_size
        except OSError:
            size = None

    if compute_hash and sha256 is None:
        log.info("Calculando SHA-256 de %s …", iso_path.name)
        sha256 = compute_sha256(iso_path)

    meta = existing or IsoMeta()
    meta.filename = iso_path.name
    meta.catalog_id = catalog_id or meta.catalog_id
    meta.local_version = local_version if local_version is not None else meta.local_version
    meta.source_url = source_url or meta.source_url
    meta.tool = "ventoy-iso-check"
    meta.tool_version = __version__
    meta.size = size if size is not None else meta.size
    if note:
        meta.note = note
    if sha256:
        meta.sha256 = sha256
    if downloaded_at is not None:
        meta.downloaded_at = downloaded_at.astimezone(UTC).isoformat()
    elif not meta.downloaded_at:
        # Prefer file mtime as best guess when sealing existing files
        try:
            mtime = datetime.fromtimestamp(iso_path.stat().st_mtime, tz=UTC)
            meta.downloaded_at = mtime.isoformat()
        except OSError:
            meta.downloaded_at = now.isoformat()

    save_meta(iso_path, meta)
    return meta


def seal_tree(
    root: Path,
    *,
    extensions: set[str] | None = None,
    only_missing: bool = True,
    compute_hash: bool = False,
    max_files: int | None = None,
    recently_modified_minutes: float | None = None,
) -> list[Path]:
    """Write sidecars for ISOs under root. Returns paths of sidecars written."""
    from ventoy_iso_check.catalog import load_catalog, match_entry

    exts = extensions or {".iso", ".img"}
    entries, defaults = load_catalog()
    skip = set(defaults.get("skip_dir_names") or [])
    written: list[Path] = []
    now = datetime.now(UTC)
    count = 0

    for dirpath, dirnames, filenames in root.resolve().walk(on_error=lambda _e: None):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        for name in filenames:
            path = dirpath / name
            if path.suffix.lower() not in exts:
                continue
            if only_missing and sidecar_path(path).is_file():
                continue
            if recently_modified_minutes is not None:
                try:
                    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                    age_min = (now - mtime).total_seconds() / 60.0
                    if age_min > recently_modified_minutes:
                        continue
                except OSError:
                    continue
            entry, ver = match_entry(name, entries)
            write_meta_for_iso(
                path,
                catalog_id=entry.id if entry else None,
                local_version=ver,
                compute_hash=compute_hash,
                note="sealed by ventoy-iso-check",
            )
            written.append(sidecar_path(path))
            count += 1
            if max_files is not None and count >= max_files:
                return written
    return written
