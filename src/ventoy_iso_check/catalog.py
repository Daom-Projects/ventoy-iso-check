from __future__ import annotations

import re
from pathlib import Path

import yaml

from ventoy_iso_check.models import CatalogEntry


def default_catalog_path() -> Path:
    from ventoy_iso_check.paths import project_root

    root = project_root()
    candidate = root / "catalog.yaml"
    if candidate.is_file():
        return candidate
    # fallback: next to this package (dev / alternate layouts)
    return Path(__file__).resolve().parents[2] / "catalog.yaml"


def load_catalog(path: Path | None = None) -> tuple[list[CatalogEntry], dict]:
    catalog_path = path or default_catalog_path()
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    defaults = data.get("defaults") or {}
    entries: list[CatalogEntry] = []
    for raw in data.get("entries") or []:
        entries.append(
            CatalogEntry(
                id=raw["id"],
                label=raw.get("label") or raw["id"],
                patterns=list(raw.get("patterns") or []),
                managed_by=raw.get("managed_by") or "manual",
                page=raw.get("page"),
                resolver=raw.get("resolver") or "none",
                sisou_updater=raw.get("sisou_updater"),
                edition=raw.get("edition"),
                arch=raw.get("arch"),
                note=raw.get("note"),
                direct_url_template=raw.get("direct_url_template"),
            )
        )
    return entries, defaults


def match_entry(
    filename: str, entries: list[CatalogEntry]
) -> tuple[CatalogEntry | None, str | None]:
    """Return (entry, local_version) if any pattern matches."""
    for entry in entries:
        for pattern in entry.patterns:
            m = re.search(pattern, filename)
            if not m:
                continue
            version = None
            if m.lastindex:
                parts = [g for g in m.groups() if g]
                # Prefer numeric-looking first group as version; append only
                # numeric-ish extras (e.g. zorin r3 → 18-3 already captured).
                if parts:
                    version = parts[0]
                    # Zorin: major + optional revision number
                    if entry.id == "zorin" and len(parts) > 1:
                        version = "-".join(parts)
                    # Pop!_OS: series + flavor + build → 24.04-nvidia-r27
                    if entry.id == "popos" and len(parts) >= 3:
                        version = f"{parts[0]}-{parts[1]}-r{parts[2]}"
                    elif entry.id == "popos" and len(parts) == 1:
                        version = parts[0]
            return entry, version
    return None, None
