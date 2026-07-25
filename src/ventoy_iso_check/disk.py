from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SpaceVerdict(str, Enum):
    OK = "ok"
    WARN = "warn"
    ABORT = "abort"
    UNKNOWN = "unknown"


@dataclass
class DiskSpace:
    path: Path
    total: int
    used: int
    free: int

    @property
    def free_gib(self) -> float:
        return self.free / (1024**3)

    @property
    def total_gib(self) -> float:
        return self.total / (1024**3)

    @property
    def used_gib(self) -> float:
        return self.used / (1024**3)

    @property
    def free_pct(self) -> float:
        if self.total <= 0:
            return 0.0
        return 100.0 * self.free / self.total


def disk_usage(path: Path) -> DiskSpace:
    """Return total/used/free bytes for the filesystem containing ``path``."""
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(str(path))
    usage = shutil.disk_usage(path)
    return DiskSpace(
        path=path,
        total=usage.total,
        used=usage.used,
        free=usage.free,
    )


def format_bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PiB"


def assess_free_space(
    space: DiskSpace,
    *,
    warn_gib: float = 8.0,
    abort_gib: float = 2.0,
) -> SpaceVerdict:
    """Compare free space against warn/abort thresholds (GiB)."""
    free = space.free_gib
    if free < abort_gib:
        return SpaceVerdict.ABORT
    if free < warn_gib:
        return SpaceVerdict.WARN
    return SpaceVerdict.OK


def check_download_space(
    ventoy_root: Path,
    *,
    warn_gib: float = 8.0,
    abort_gib: float = 2.0,
    force: bool = False,
) -> tuple[DiskSpace | None, SpaceVerdict, str]:
    """Evaluate free space before download.

    Returns (space|None, verdict, human message).
    On ABORT without force, caller should exit non-zero.
    """
    try:
        space = disk_usage(ventoy_root)
    except OSError as e:
        return (
            None,
            SpaceVerdict.UNKNOWN,
            f"No se pudo leer espacio en {ventoy_root}: {e}",
        )

    verdict = assess_free_space(space, warn_gib=warn_gib, abort_gib=abort_gib)
    msg = (
        f"Espacio en {space.path}: "
        f"libre {format_bytes(space.free)} ({space.free_gib:.2f} GiB, "
        f"{space.free_pct:.1f}%) / total {format_bytes(space.total)}"
    )

    if verdict == SpaceVerdict.ABORT:
        msg += (
            f"\n[ABORT] Libre < {abort_gib:.1f} GiB. "
            "Libera espacio o usa --force para continuar de todos modos."
        )
        if force:
            msg += " (--force: se continúa de todos modos)"
            verdict = SpaceVerdict.WARN
    elif verdict == SpaceVerdict.WARN:
        msg += (
            f"\n[WARN] Libre < {warn_gib:.1f} GiB. "
            "Una ISO grande (Ubuntu ~6 GiB, Kali ~4.5 GiB) puede no caber."
        )

    return space, verdict, msg
