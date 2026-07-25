from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ventoy_iso_check.models import CatalogEntry
from ventoy_iso_check.resolvers import ResolveResult

log = logging.getLogger(__name__)

DEFAULT_TTL_HOURS = 12
CACHE_SCHEMA = 1


def default_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "ventoy-iso-check"
    return Path.home() / ".cache" / "ventoy-iso-check"


def default_cache_file(cache_dir: Path | None = None) -> Path:
    return (cache_dir or default_cache_dir()) / "latest.json"


def cache_key(
    entry: CatalogEntry,
    local_version: str | None,
    policy: str | None = None,
) -> str:
    """Key for a resolve lookup (local version + upgrade policy affect target)."""
    parts = [
        entry.id,
        entry.resolver or "none",
        entry.edition or "",
        entry.arch or "",
        local_version or "",
        policy or "latest-lts",
    ]
    return "|".join(parts)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


@dataclass
class CacheEntry:
    fetched_at: str
    latest_version: str | None = None
    download_url: str | None = None
    page: str | None = None
    note: str | None = None
    error: str | None = None

    def to_resolve_result(self) -> ResolveResult:
        return ResolveResult(
            latest_version=self.latest_version,
            download_url=self.download_url,
            page=self.page,
            note=self.note,
            error=self.error,
        )

    @classmethod
    def from_resolve_result(cls, result: ResolveResult, fetched_at: datetime) -> CacheEntry:
        return cls(
            fetched_at=fetched_at.isoformat(),
            latest_version=result.latest_version,
            download_url=result.download_url,
            page=result.page,
            note=result.note,
            error=result.error,
        )


class ResolveCache:
    """JSON file cache for ResolveResult with TTL."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        ttl_hours: float = DEFAULT_TTL_HOURS,
        enabled: bool = True,
        refresh: bool = False,
    ) -> None:
        self.path = path or default_cache_file()
        self.ttl = timedelta(hours=ttl_hours)
        self.enabled = enabled
        self.refresh = refresh  # skip reads, still write
        self._data: dict[str, Any] = {"schema": CACHE_SCHEMA, "entries": {}}
        self.hits = 0
        self.misses = 0
        self.stores = 0
        if self.enabled:
            self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            entries = raw.get("entries") or {}
            if not isinstance(entries, dict):
                return
            self._data = {"schema": CACHE_SCHEMA, "entries": entries}
            log.debug("Cache loaded: %s (%d keys)", self.path, len(entries))
        except (OSError, json.JSONDecodeError) as e:
            log.warning("No se pudo leer cache %s: %s", self.path, e)

    def save(self) -> None:
        if not self.enabled:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._data["schema"] = CACHE_SCHEMA
            self._data["updated_at"] = _utc_now().isoformat()
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self.path)
            log.debug("Cache saved: %s", self.path)
        except OSError as e:
            log.warning("No se pudo escribir cache %s: %s", self.path, e)

    def get(self, key: str) -> ResolveResult | None:
        if not self.enabled or self.refresh:
            self.misses += 1
            return None
        raw = (self._data.get("entries") or {}).get(key)
        if not isinstance(raw, dict):
            self.misses += 1
            return None
        fetched = _parse_ts(raw.get("fetched_at"))
        if fetched is None or _utc_now() - fetched > self.ttl:
            self.misses += 1
            log.debug("Cache miss/expired: %s", key)
            return None
        self.hits += 1
        log.debug("Cache hit: %s", key)
        return CacheEntry(
            fetched_at=raw.get("fetched_at") or "",
            latest_version=raw.get("latest_version"),
            download_url=raw.get("download_url"),
            page=raw.get("page"),
            note=raw.get("note"),
            error=raw.get("error"),
        ).to_resolve_result()

    def set(self, key: str, result: ResolveResult) -> None:
        if not self.enabled:
            return
        # Don't cache hard failures forever as success — still cache briefly is ok
        entry = CacheEntry.from_resolve_result(result, _utc_now())
        self._data.setdefault("entries", {})[key] = asdict(entry)
        self.stores += 1

    def stats_line(self) -> str:
        return (
            f"cache hits={self.hits} misses={self.misses} stores={self.stores} "
            f"file={self.path} ttl={self.ttl.total_seconds() / 3600:.1f}h"
        )
