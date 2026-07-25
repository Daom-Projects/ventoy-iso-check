from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ventoy_iso_check.bootloaders import (
    _find_etcher,
    _find_rufus,
    check_bootloaders,
    format_bootloaders_console,
)


def test_find_rufus_and_etcher(tmp_path: Path):
    boot = tmp_path / "Bootloaders"
    boot.mkdir()
    (boot / "rufus-4.15p.exe").write_bytes(b"MZ")
    (boot / "balenaEtcher-2.1.6.Setup.exe").write_bytes(b"MZ")
    (boot / "balenaEtcher-linux-x64-2.1.6.zip").write_bytes(b"PK")

    r = _find_rufus(boot)
    assert r.local_version == "4.15"
    assert r.local_path and "rufus-4.15p" in r.local_path

    e = _find_etcher(boot)
    assert e.local_version == "2.1.6"
    assert e.local_path


def test_check_bootloaders_offline(tmp_path: Path):
    boot = tmp_path / "Bootloaders"
    vdir = boot / "ventoy-1.1.17" / "ventoy"
    vdir.mkdir(parents=True)
    (vdir / "version").write_text("1.1.17\n", encoding="utf-8")
    (boot / "rufus-4.15p.exe").write_bytes(b"MZ")

    tools = check_bootloaders(tmp_path, online=False)
    ids = {t.id for t in tools}
    assert "ventoy" in ids and "rufus" in ids and "balena-etcher" in ids
    ventoy = next(t for t in tools if t.id == "ventoy")
    assert ventoy.local_version == "1.1.17"
    text = format_bootloaders_console(tools)
    assert "Rufus" in text and "Ventoy" in text


def test_check_bootloaders_online_ok(tmp_path: Path):
    boot = tmp_path / "Bootloaders"
    vdir = boot / "ventoy-1.1.17" / "ventoy"
    vdir.mkdir(parents=True)
    (vdir / "version").write_text("1.1.17\n", encoding="utf-8")
    (boot / "rufus-4.15p.exe").write_bytes(b"MZ")
    (boot / "balenaEtcher-2.1.6.Setup.exe").write_bytes(b"MZ")

    with (
        patch(
            "ventoy_iso_check.bootloaders.check_ventoy",
            return_value=type(
                "V",
                (),
                {
                    "local_version": "1.1.17",
                    "local_path": str(vdir / "version"),
                    "latest_version": "1.1.17",
                    "latest_url": "https://example.com",
                    "status": "OK",
                    "note": "ok",
                },
            )(),
        ),
        patch(
            "ventoy_iso_check.bootloaders.fetch_latest_rufus",
            return_value=("4.15", "https://rufus.ie", None),
        ),
        patch(
            "ventoy_iso_check.bootloaders.fetch_latest_etcher",
            return_value=("2.1.6", "https://github.com/balena-io/etcher", None),
        ),
    ):
        tools = check_bootloaders(tmp_path, online=True)

    by_id = {t.id: t for t in tools}
    assert by_id["rufus"].status == "OK"
    assert by_id["balena-etcher"].status == "OK"
