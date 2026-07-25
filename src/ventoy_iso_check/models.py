from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    OK = "OK"
    OUTDATED = "OUTDATED"
    UNKNOWN = "UNKNOWN"
    MANUAL = "MANUAL"
    UNSUPPORTED = "UNSUPPORTED"
    ERROR = "ERROR"


@dataclass
class CatalogEntry:
    id: str
    label: str
    patterns: list[str]
    managed_by: str  # sisou | catalog | manual
    page: str | None = None
    resolver: str = "none"
    sisou_updater: str | None = None
    edition: str | None = None
    arch: str | None = None
    note: str | None = None
    direct_url_template: str | None = None


@dataclass
class IsoItem:
    path: Path
    relpath: str
    size: int
    filename: str
    catalog_id: str | None = None
    label: str | None = None
    local_version: str | None = None
    latest_version: str | None = None
    status: Status = Status.UNKNOWN
    managed_by: str = "unsupported"
    download_url: str | None = None
    page: str | None = None
    note: str | None = None
    sisou_updater: str | None = None
    # Timestamps from the filesystem (local file on the Ventoy volume)
    mtime: datetime | None = None  # last modification — usually copy/download time
    birthtime: datetime | None = None  # creation if the FS exposes it
    age_days: float | None = None
    # Sidecar metadata (foo.iso.meta.json)
    has_meta: bool = False
    meta_downloaded_at: datetime | None = None
    meta_sha256: str | None = None
    meta_source_url: str | None = None
    checksum_ok: bool | None = None  # None = not verified
    date_source: str = "mtime"  # "meta" | "birthtime" | "mtime"
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        def _iso(dt: datetime | None) -> str | None:
            if dt is None:
                return None
            return dt.isoformat()

        return {
            "path": str(self.path),
            "relpath": self.relpath,
            "size": self.size,
            "filename": self.filename,
            "catalog_id": self.catalog_id,
            "label": self.label,
            "local_version": self.local_version,
            "latest_version": self.latest_version,
            "status": self.status.value,
            "managed_by": self.managed_by,
            "download_url": self.download_url,
            "page": self.page,
            "note": self.note,
            "sisou_updater": self.sisou_updater,
            "mtime": _iso(self.mtime),
            "birthtime": _iso(self.birthtime),
            "age_days": self.age_days,
            "file_date": self.file_date_str(),
            "age_label": self.age_label(),
            "has_meta": self.has_meta,
            "meta_downloaded_at": _iso(self.meta_downloaded_at),
            "meta_sha256": self.meta_sha256,
            "meta_source_url": self.meta_source_url,
            "checksum_ok": self.checksum_ok,
            "date_source": self.date_source,
        }

    def file_date_str(self) -> str:
        """Prefer meta downloaded_at, then birthtime, then mtime."""
        dt = self.meta_downloaded_at or self.birthtime or self.mtime
        if not dt:
            return "—"
        return dt.astimezone().strftime("%Y-%m-%d")

    def age_label(self) -> str:
        if self.age_days is None:
            return "—"
        d = self.age_days
        if d < 1:
            hours = max(1, int(d * 24))
            return f"{hours}h"
        if d < 45:
            return f"{int(d)}d"
        if d < 365:
            return f"{d / 30:.1f}mo"
        return f"{d / 365:.1f}y"

    def meta_label(self) -> str:
        if not self.has_meta:
            return "—"
        if self.checksum_ok is True:
            return "✓ sha"
        if self.checksum_ok is False:
            return "✗ sha"
        if self.meta_sha256:
            return "✓ hash"
        return "✓"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def from_timestamp(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None
