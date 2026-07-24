from __future__ import annotations

from pathlib import Path

from ventoy_iso_check.catalog import match_entry
from ventoy_iso_check.models import CatalogEntry, IsoItem, Status


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

    items: list[IsoItem] = []

    for dirpath, dirnames, filenames in root.walk(on_error=lambda _e: None):
        # prune directories in-place
        dirnames[:] = [
            d
            for d in dirnames
            if d not in skip and not d.startswith(".")
        ]

        # avoid walking extremely deep vendor trees
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
            try:
                size = path.stat().st_size
            except OSError:
                size = 0

            relpath = str(path.relative_to(root))
            entry, local_version = match_entry(name, entries)

            item = IsoItem(
                path=path,
                relpath=relpath,
                size=size,
                filename=name,
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

            items.append(item)

    items.sort(key=lambda i: i.relpath.lower())
    return items
