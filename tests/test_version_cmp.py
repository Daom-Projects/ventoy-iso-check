from __future__ import annotations

from ventoy_iso_check.version_cmp import is_outdated, versions_comparable


def test_equal_versions():
    assert is_outdated("24.04.4", "24.04.4") is False
    assert is_outdated("26.04", "26.04") is False


def test_outdated_point_and_major():
    assert is_outdated("24.04.3", "24.04.4") is True
    assert is_outdated("24.04.4", "26.04") is True
    assert is_outdated("43-1.6", "44-1.7") is True


def test_up_to_date_newer_local():
    assert is_outdated("26.04", "24.04.4") is False


def test_lts_suffix_and_codenames():
    assert is_outdated("24.04.4", "24.04.4 LTS") is False
    assert is_outdated("2.6.1-plucky", "2.6.2") is True


def test_popos_style():
    assert is_outdated("24.04-nvidia-r20", "24.04-r27") is True
    assert is_outdated("24.04-nvidia-r27", "24.04-r27") is False


def test_missing_versions():
    assert is_outdated(None, "1.0") is None
    assert is_outdated("1.0", None) is None


def test_comparable():
    assert versions_comparable("1.2.3", "1.2.4") is True
