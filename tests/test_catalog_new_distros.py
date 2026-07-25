"""Catalog coverage for workshop distros not necessarily on the USB."""

from __future__ import annotations

from ventoy_iso_check.catalog import load_catalog, match_entry
from ventoy_iso_check.resolvers import RESOLVERS


def test_new_distro_entries_present():
    entries, _ = load_catalog()
    ids = {e.id for e in entries}
    expected = {
        "kubuntu",
        "manjaro-xfce",
        "manjaro-kde",
        "opensuse-leap",
        "opensuse-tumbleweed",
        "rocky-dvd",
        "rocky-minimal",
        "almalinux-dvd",
        "alpine-standard",
        "mxlinux",
        "supergrub2",
        "garuda",
        "debian-netinst",
        "archlinux",
        "gparted-live",
        "memtest86plus",
    }
    missing = expected - ids
    assert not missing, f"Faltan en catalog.yaml: {missing}"


def test_new_resolvers_registered():
    for name in (
        "manjaro",
        "opensuse",
        "rocky",
        "almalinux",
        "alpine",
        "mxlinux",
        "supergrub2",
        "kubuntu",
        "garuda",
    ):
        assert name in RESOLVERS


def test_match_sample_filenames():
    entries, _ = load_catalog()
    samples = [
        ("kubuntu-24.04.2-desktop-amd64.iso", "kubuntu", "24.04.2"),
        ("manjaro-xfce-24.2.1-241209-linux612-x86_64.iso", "manjaro-xfce", "24.2.1"),
        ("openSUSE-Leap-15.6-DVD-x86_64-Media.iso", "opensuse-leap", "15.6"),
        ("Rocky-9.5-x86_64-dvd.iso", "rocky-dvd", "9.5"),
        ("AlmaLinux-9.5-x86_64-dvd.iso", "almalinux-dvd", "9.5"),
        ("alpine-standard-3.21.0-x86_64.iso", "alpine-standard", "3.21.0"),
        ("debian-12.10.0-amd64-netinst.iso", "debian-netinst", "12.10.0"),
        ("archlinux-2026.07.01-x86_64.iso", "archlinux", "2026.07.01"),
        ("gparted-live-1.7.0-1-amd64.iso", "gparted-live", "1.7.0-1"),
    ]
    for fname, expect_id, expect_ver in samples:
        entry, ver = match_entry(fname, entries)
        assert entry is not None, f"no match for {fname}"
        assert entry.id == expect_id, f"{fname} → {entry.id} (want {expect_id})"
        if expect_ver:
            assert ver == expect_ver or (ver and expect_ver in ver), (
                f"{fname} ver={ver} want {expect_ver}"
            )
