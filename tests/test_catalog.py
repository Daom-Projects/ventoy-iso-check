from __future__ import annotations

from ventoy_iso_check.catalog import load_catalog, match_entry


def test_load_catalog_has_core_entries(catalog_entries):
    entries, defaults = catalog_entries
    ids = {e.id for e in entries}
    assert "ubuntu-desktop" in ids
    assert "ubuntu-live-server" in ids
    assert "fedora-workstation" in ids
    assert "debian-netinst" in ids
    assert "archlinux" in ids
    assert ".iso" in (defaults.get("extensions") or [".iso"])


def test_match_ubuntu_and_fedora(catalog_entries):
    entries, _ = catalog_entries
    e, v = match_entry("ubuntu-26.04-desktop-amd64.iso", entries)
    assert e is not None and e.id == "ubuntu-desktop"
    assert v == "26.04"

    e, v = match_entry("ubuntu-24.04.4-live-server-amd64.iso", entries)
    assert e is not None and e.id == "ubuntu-live-server"
    assert v == "24.04.4"

    e, v = match_entry("Fedora-Workstation-Live-44-1.7.x86_64.iso", entries)
    assert e is not None and e.id == "fedora-workstation"
    assert v == "44-1.7"


def test_match_pop_mint_win11(catalog_entries):
    entries, _ = catalog_entries
    e, v = match_entry("pop-os_24.04_amd64_nvidia_27.iso", entries)
    assert e is not None and e.id == "popos"
    assert v == "24.04-nvidia-r27"

    e, v = match_entry("linuxmint-22.3-mate-64bit.iso", entries)
    assert e is not None and e.id == "linuxmint-mate"
    assert v == "22.3"

    e, v = match_entry("Win11_es-mx_25H2_july_2026_x64.iso", entries)
    assert e is not None and e.id == "windows11"
    assert v == "25H2"


def test_unknown_filename(catalog_entries):
    entries, _ = catalog_entries
    e, v = match_entry("totally-unknown-os-99.iso", entries)
    assert e is None
    assert v is None
