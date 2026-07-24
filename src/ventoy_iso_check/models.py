from __future__ import annotations

from dataclasses import dataclass, field
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
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
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
        }
