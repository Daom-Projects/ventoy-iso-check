from __future__ import annotations

from pathlib import Path

import pytest

from ventoy_iso_check.catalog import load_catalog


@pytest.fixture
def catalog_entries():
    entries, defaults = load_catalog()
    return entries, defaults


@pytest.fixture
def sample_meta_release() -> str:
    """Minimal Ubuntu meta-release fixture (Supported releases only)."""
    return """
Dist: jammy
Name: Jammy Jellyfish
Version: 22.04.5 LTS
Supported: 1
Description: Ubuntu 22.04.5 LTS

Dist: noble
Name: Noble Numbat
Version: 24.04.4 LTS
Supported: 1
Description: Ubuntu 24.04.4 LTS

Dist: plucky
Name: Plucky Puffin
Version: 25.04
Supported: 0
Description: unsupported interim

Dist: resolute
Name: Resolute Raccoon
Version: 26.04 LTS
Supported: 1
Description: Ubuntu 26.04 LTS

Dist: questing
Name: Questing Quokka
Version: 25.10
Supported: 1
Description: Ubuntu 25.10 interim supported
""".strip()


@pytest.fixture
def tmp_iso_tree(tmp_path: Path) -> Path:
    linux = tmp_path / "Linux"
    linux.mkdir()
    (linux / "ubuntu-24.04.4-live-server-amd64.iso").write_bytes(b"iso")
    (linux / "ubuntu-26.04-desktop-amd64.iso").write_bytes(b"iso")
    (linux / "Fedora-Workstation-Live-44-1.7.x86_64.iso").write_bytes(b"iso")
    (linux / "unknown-distro-1.0.iso").write_bytes(b"iso")
    tools = tmp_path / "Herramientas"
    tools.mkdir()
    (tools / "clonezilla-live-3.3.3-15-amd64.iso").write_bytes(b"iso")
    return tmp_path
