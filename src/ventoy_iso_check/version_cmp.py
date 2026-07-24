from __future__ import annotations

import re

from packaging.version import InvalidVersion, Version


def _normalize(v: str) -> str:
    v = v.strip()
    v = re.sub(r"\s*LTS\s*", "", v, flags=re.I)
    # Drop codename suffixes: 2.6.1-plucky → 2.6.1
    v = re.sub(r"-(noble|resolute|plucky|bionic|jammy|focal)(\b|$)", "", v, flags=re.I)
    # Fedora style 43-1.6 → 43.1.6 for comparison
    v = v.replace("_", ".")
    # Proxmox / clonezilla style keep hyphens as dots for packaging.Version
    v = v.replace("-", ".")
    v = re.sub(r"[^0-9A-Za-z.]+", ".", v)
    v = re.sub(r"\.+", ".", v).strip(".")
    return v


def versions_comparable(a: str, b: str) -> bool:
    try:
        Version(_normalize(a))
        Version(_normalize(b))
        return True
    except InvalidVersion:
        return False


def is_outdated(local: str | None, latest: str | None) -> bool | None:
    """Return True if local < latest, False if up-to-date, None if unknown."""
    if not local or not latest:
        return None
    if local == latest:
        return False
    try:
        return Version(_normalize(local)) < Version(_normalize(latest))
    except InvalidVersion:
        # fallback: string inequality only signals possible update if different
        return local != latest
