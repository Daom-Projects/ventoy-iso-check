from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ventoy_iso_check.cache import ResolveCache, cache_key
from ventoy_iso_check.catalog import load_catalog, match_entry
from ventoy_iso_check.inventory import scan_isos
from ventoy_iso_check.meta import verify_sha256
from ventoy_iso_check.models import CatalogEntry, IsoItem, Status
from ventoy_iso_check.policy import UpgradePolicy
from ventoy_iso_check.resolvers import ResolveResult, resolve
from ventoy_iso_check.version_cmp import is_outdated

log = logging.getLogger(__name__)

DEFAULT_RESOLVE_WORKERS = 8


def run_check(
    root: Path,
    *,
    catalog_path: Path | None = None,
    deep: bool = False,
    online: bool = True,
    only: set[str] | None = None,
    cache: ResolveCache | None = None,
    verify_checksum: bool = False,
    policy: UpgradePolicy | str = UpgradePolicy.LATEST_LTS,
    hint_newer: bool = False,
    max_workers: int = DEFAULT_RESOLVE_WORKERS,
) -> list[IsoItem]:
    if isinstance(policy, str):
        policy = UpgradePolicy.parse(policy)
    entries, defaults = load_catalog(catalog_path)
    skip = set(defaults.get("skip_dir_names") or [])
    exts = set(defaults.get("extensions") or [".iso", ".img"])

    items = scan_isos(
        root,
        entries,
        extensions=exts,
        skip_dirs=skip or None,
        deep=deep,
    )

    if only:
        only_l = {o.lower() for o in only}
        items = [
            i
            for i in items
            if (i.catalog_id and i.catalog_id.lower() in only_l)
            or (i.label and i.label.lower() in only_l)
            or any(o in i.filename.lower() for o in only_l)
        ]

    by_id = {e.id: e for e in entries}
    dirty = False

    # Classify items; collect those needing network resolve
    pending: list[tuple[IsoItem, CatalogEntry, str]] = []

    for item in items:
        if item.managed_by == "manual":
            item.status = Status.MANUAL
            continue
        if item.managed_by == "unsupported" or not item.catalog_id:
            item.status = Status.UNSUPPORTED
            continue
        if not online:
            item.status = Status.UNKNOWN
            continue

        entry = by_id.get(item.catalog_id or "")
        if not entry:
            item.status = Status.UNSUPPORTED
            continue

        if entry.resolver in (None, "none") and entry.managed_by == "sisou":
            item.status = Status.UNKNOWN
            item.note = item.note or "Usar sisou para comprobar/actualizar esta ISO"
            continue

        key = cache_key(entry, item.local_version, policy=policy.value)
        cached = cache.get(key) if cache else None
        if cached is not None:
            _apply_resolve_result(item, cached)
            continue

        pending.append((item, entry, key))

    if pending:
        workers = max(1, min(max_workers, len(pending)))

        def _job(
            pair: tuple[IsoItem, CatalogEntry, str],
        ) -> tuple[IsoItem, str, ResolveResult]:
            it, ent, k = pair
            res = resolve(
                ent,
                it.local_version,
                policy=policy,
                hint_newer=hint_newer,
            )
            return it, k, res

        if workers == 1:
            results = [_job(p) for p in pending]
        else:
            results = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [pool.submit(_job, p) for p in pending]
                for fut in as_completed(futs):
                    results.append(fut.result())

        for item, key, result in results:
            if cache is not None:
                cache.set(key, result)
                dirty = True
            _apply_resolve_result(item, result)

    if verify_checksum:
        _apply_checksum_verification(items)

    if cache is not None and dirty:
        cache.save()

    return items


def _apply_resolve_result(item: IsoItem, result: ResolveResult) -> None:
    if result.error:
        log.warning("%s: %s", item.filename, result.error)
        item.status = Status.ERROR
        item.note = result.error
        if result.page:
            item.page = result.page
        return

    item.latest_version = result.latest_version
    item.download_url = result.download_url
    if result.page:
        item.page = result.page
    if result.note:
        item.note = result.note

    outdated = is_outdated(item.local_version, item.latest_version)
    if outdated is True:
        item.status = Status.OUTDATED
    elif outdated is False:
        item.status = Status.OK
    else:
        item.status = Status.UNKNOWN


def _apply_checksum_verification(items: list[IsoItem]) -> None:
    """Verify SHA-256 from sidecar when present. Never deletes the ISO."""
    for item in items:
        if not item.meta_sha256:
            continue
        log.info("Verificando SHA-256: %s", item.filename)
        try:
            ok, actual = verify_sha256(item.path, item.meta_sha256)
        except OSError as e:
            item.checksum_ok = False
            item.status = Status.ERROR
            item.note = f"No se pudo leer para checksum: {e}"
            continue
        item.checksum_ok = ok
        if not ok:
            item.status = Status.ERROR
            item.note = (
                f"SHA-256 no coincide (meta={item.meta_sha256[:16]}… "
                f"actual={actual[:16]}…). ISO no borrada."
            )
            log.error("%s: checksum mismatch", item.filename)


def entry_for_filename(filename: str, catalog_path: Path | None = None) -> CatalogEntry | None:
    entries, _ = load_catalog(catalog_path)
    entry, _ = match_entry(filename, entries)
    return entry
