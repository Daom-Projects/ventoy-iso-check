from __future__ import annotations

from pathlib import Path

from ventoy_iso_check.paths import (
    find_ventoy_root_from,
    looks_like_ventoy_root,
)


def test_looks_like_ventoy_root(tmp_path: Path):
    assert not looks_like_ventoy_root(tmp_path)
    (tmp_path / "Linux").mkdir()
    (tmp_path / "Herramientas").mkdir()
    (tmp_path / "Linux" / "ubuntu.iso").write_bytes(b"x")
    assert looks_like_ventoy_root(tmp_path)


def test_find_from_scripts_subfolder(tmp_path: Path):
    # E:\ style: root has Linux + Bootloaders; tool in Scripts/ventoy-iso-check
    root = tmp_path / "USB"
    root.mkdir()
    (root / "Linux").mkdir()
    (root / "Bootloaders").mkdir()
    (root / "Bootloaders" / "ventoy-1.1.17").mkdir()
    (root / "Linux" / "x.iso").write_bytes(b"iso")
    tool = root / "Scripts" / "ventoy-iso-check"
    tool.mkdir(parents=True)
    (tool / "catalog.yaml").write_text("entries: []\n", encoding="utf-8")
    (tool / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    assert looks_like_ventoy_root(root)
    # El repo solo no debe contarse como raíz Ventoy
    assert not looks_like_ventoy_root(tool)

    found = find_ventoy_root_from(tool)
    assert found is not None
    assert found.resolve() == root.resolve()
