from __future__ import annotations

from pathlib import Path

from ventoy_iso_check.meta import (
    compute_sha256,
    load_meta,
    sidecar_path,
    verify_sha256,
    write_meta_for_iso,
)
from ventoy_iso_check.suggest import format_suggestions, suggest_unsupported


def test_meta_write_load_and_hash(tmp_path: Path):
    iso = tmp_path / "ubuntu-26.04-desktop-amd64.iso"
    iso.write_bytes(b"hello-iso")
    meta = write_meta_for_iso(
        iso,
        catalog_id="ubuntu-desktop",
        local_version="26.04",
        source_url="https://example.com/u.iso",
        compute_hash=True,
    )
    assert sidecar_path(iso).is_file()
    loaded = load_meta(iso)
    assert loaded is not None
    assert loaded.catalog_id == "ubuntu-desktop"
    assert loaded.sha256 == compute_sha256(iso)
    ok, actual = verify_sha256(iso, loaded.sha256 or "")
    assert ok and actual == loaded.sha256

    iso.write_bytes(b"corrupted")
    ok2, _ = verify_sha256(iso, meta.sha256 or "")
    assert ok2 is False


def test_suggest_unsupported(tmp_path: Path):
    linux = tmp_path / "Linux"
    linux.mkdir()
    (linux / "totally-new-os-3.2.1.iso").write_bytes(b"x")
    (linux / "ubuntu-26.04-desktop-amd64.iso").write_bytes(b"x")  # known
    suggestions = suggest_unsupported(tmp_path)
    assert len(suggestions) >= 1
    ids = {s.suggested_id for s in suggestions}
    assert any("totally" in i or "new-os" in i for i in ids)
    text = format_suggestions(suggestions)
    assert "managed_by:" in text
    assert "patterns:" in text
