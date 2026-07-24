from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ventoy_iso_check.paths import project_root

log = logging.getLogger(__name__)


def default_sisou_toml() -> Path:
    return project_root() / "sisou.toml"


def find_uv() -> str | None:
    return shutil.which("uv")


def find_sisou() -> str | None:
    """Sisou instalado en PATH (p. ej. imagen Docker con pip install sisou)."""
    return shutil.which("sisou")


def materialize_sisou_config(
    template: Path,
    ventoy_root: Path,
    *,
    dest: Path | None = None,
) -> Path:
    """Copia sisou.toml reescribiendo ``directory = ...`` a la raíz Ventoy real."""
    text = template.read_text(encoding="utf-8")
    root_str = str(ventoy_root.resolve())
    # Replace first top-level directory assignment only
    new_text, n = re.subn(
        r'(?m)^directory\s*=\s*["\'][^"\']*["\']',
        f'directory = "{root_str}"',
        text,
        count=1,
    )
    if n == 0:
        # prepend if missing
        new_text = f'directory = "{root_str}"\n\n' + text

    if dest is None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix="-sisou.toml",
            prefix="ventoy-iso-check-",
            delete=False,
            encoding="utf-8",
        )
        tmp.write(new_text)
        tmp.close()
        return Path(tmp.name)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(new_text, encoding="utf-8")
    return dest


def run_sisou(
    config: Path,
    *,
    ventoy_root: Path | None = None,
    log_level: str = "INFO",
    dry_run: bool = False,
) -> int:
    """Invoke SuperISOUpdater (sisou on PATH, or via uv tool run + Python 3.12)."""
    config = config.resolve()
    if not config.exists():
        log.error("No existe sisou.toml: %s", config)
        return 2

    effective = config
    temp_config: Path | None = None
    if ventoy_root is not None:
        temp_config = materialize_sisou_config(config, ventoy_root)
        effective = temp_config
        log.info("sisou.toml materializado con directory=%s → %s", ventoy_root, effective)

    sisou_bin = find_sisou()
    if sisou_bin:
        cmd = [sisou_bin, str(effective), "-l", log_level]
    else:
        uv = find_uv()
        if not uv:
            log.error(
                "Ni `sisou` ni `uv` están en PATH. "
                "Instala uv o usa la imagen Docker del proyecto."
            )
            if temp_config:
                temp_config.unlink(missing_ok=True)
            return 127
        cmd = [
            uv,
            "tool",
            "run",
            "--python",
            "3.12",
            "sisou@latest",
            str(effective),
            "-l",
            log_level,
        ]

    if dry_run:
        log.info("[dry-run] Ejecutaría: %s", " ".join(cmd))
        print(f"[dry-run] {' '.join(cmd)}")
        if ventoy_root:
            print(f"[dry-run] directory (Ventoy) = {ventoy_root.resolve()}")
        print("Revisa/edita sisou.toml antes de una descarga real.")
        if temp_config:
            temp_config.unlink(missing_ok=True)
        return 0

    log.info("Ejecutando: %s", " ".join(cmd))
    print("Lanzando SuperISOUpdater (sisou)…")
    print(" ".join(cmd))
    try:
        proc = subprocess.run(cmd, check=False)
        return proc.returncode
    finally:
        if temp_config:
            temp_config.unlink(missing_ok=True)
