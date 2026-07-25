from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ventoy_iso_check.catalog import match_entry
from ventoy_iso_check.meta import load_meta
from ventoy_iso_check.models import (
    CatalogEntry,
    IsoItem,
    Status,
    from_timestamp,
    utc_now,
)


SKIP_DIR_DEFAULTS = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "Bootloaders",
    "MediCat.USB.v21.12",
    "windows95-win32-x64-3.1.1",
    "PortableApps",
    "Programs",
    ".git",
    ".venv",
}


def _stat_times(path: Path) -> tuple[datetime | None, datetime | None, int]:
    """Return (mtime, birthtime, size). birthtime may be None on many FS."""
    try:
        st = path.stat()
    except OSError:
        return None, None, 0

    mtime = from_timestamp(st.st_mtime)
    birth = None
    birth_ts = getattr(st, "st_birthtime", None)
    if birth_ts and birth_ts > 0:
        birth = from_timestamp(birth_ts)
    return mtime, birth, st.st_size


def scan_isos(
    root: Path,
    entries: list[CatalogEntry],
    *,
    extensions: set[str] | None = None,
    skip_dirs: set[str] | None = None,
    deep: bool = False,
) -> list[IsoItem]:
    root = root.resolve()
    exts = extensions or {".iso", ".img"}
    skip = set(skip_dirs or SKIP_DIR_DEFAULTS)
    if deep:
        skip.discard("MediCat.USB.v21.12")

    now = utc_now()
    items: list[IsoItem] = []

    for dirpath, dirnames, filenames in root.walk(on_error=lambda _e: None):
        dirnames[:] = [
            d for d in dirnames if d not in skip and not d.startswith(".")
        ]

        try:
            rel_dir = dirpath.relative_to(root)
        except ValueError:
            continue
        depth = len(rel_dir.parts)
        if not deep and depth > 4:
            dirnames.clear()
            continue

        for name in filenames:
            path = dirpath / name
            suffix = path.suffix.lower()
            if suffix not in exts:
                continue
            # never treat sidecar as ISO
            if name.endswith(".meta.json"):
                continue

            mtime, birth, size = _stat_times(path)
            meta = load_meta(path)
            meta_dt = meta.downloaded_at_dt() if meta else None

            if meta_dt is not None:
                ref = meta_dt
                date_source = "meta"
            elif birth is not None:
                ref = birth
                date_source = "birthtime"
            else:
                ref = mtime
                date_source = "mtime"

            age_days = None
            if ref is not None:
                age_days = max(0.0, (now - ref).total_seconds() / 86400.0)

            relpath = str(path.relative_to(root))
            entry, local_version = match_entry(name, entries)

            item = IsoItem(
                path=path,
                relpath=relpath,
                size=size,
                filename=name,
                mtime=mtime,
                birthtime=birth,
                age_days=age_days,
                has_meta=meta is not None,
                meta_downloaded_at=meta_dt,
                meta_sha256=meta.sha256 if meta else None,
                meta_source_url=meta.source_url if meta else None,
                date_source=date_source,
            )
            if entry:
                item.catalog_id = entry.id
                item.label = entry.label
                item.local_version = local_version
                item.managed_by = entry.managed_by
                item.page = entry.page
                item.note = entry.note
                item.sisou_updater = entry.sisou_updater
                if entry.managed_by == "manual":
                    item.status = Status.MANUAL
                else:
                    item.status = Status.UNKNOWN
            else:
                item.label = name
                item.managed_by = "unsupported"
                item.status = Status.UNSUPPORTED
                item.note = "Sin entrada en catalog.yaml"

            # Enrich from meta when useful
            if meta and meta.catalog_id and not item.catalog_id:
                item.catalog_id = meta.catalog_id
            if meta and meta.source_url and not item.download_url:
                item.download_url = meta.source_url

            items.append(item)

    items.sort(key=lambda i: i.relpath.lower())
    return items
