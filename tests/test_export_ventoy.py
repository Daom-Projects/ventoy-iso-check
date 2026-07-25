from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ventoy_iso_check.export import write_csv, write_html
from ventoy_iso_check.models import IsoItem, Status
from ventoy_iso_check.ventoy_info import (
    _find_local_version,
    check_ventoy,
)


def test_write_csv_and_html(tmp_path: Path):
    items = [
        IsoItem(
            path=tmp_path / "a.iso",
            relpath="Linux/a.iso",
            size=1024,
            filename="a.iso",
            label="A",
            local_version="1.0",
            latest_version="1.1",
            status=Status.OUTDATED,
            managed_by="catalog",
            age_days=2.0,
        )
    ]
    csv_path = tmp_path / "r.csv"
    html_path = tmp_path / "r.html"
    write_csv(items, csv_path)
    write_html(items, html_path, ventoy_section="<p>Ventoy OK</p>")
    text = csv_path.read_text(encoding="utf-8")
    assert "Linux/a.iso" in text and "OUTDATED" in text
    ht = html_path.read_text(encoding="utf-8")
    assert "OUTDATED" in ht and "Ventoy OK" in ht and "ventoy-iso-check" in ht


def test_find_local_ventoy_version(tmp_path: Path):
    vdir = tmp_path / "Bootloaders" / "ventoy-1.1.10" / "ventoy"
    vdir.mkdir(parents=True)
    (vdir / "version").write_text("1.1.10\n", encoding="utf-8")
    ver, path = _find_local_version(tmp_path)
    assert ver == "1.1.10"
    assert path is not None and path.name == "version"


def test_check_ventoy_outdated(tmp_path: Path):
    vdir = tmp_path / "Bootloaders" / "ventoy-1.0.0" / "ventoy"
    vdir.mkdir(parents=True)
    (vdir / "version").write_text("1.0.0\n", encoding="utf-8")

    def fake_latest():
        return "1.1.17", "https://github.com/ventoy/Ventoy/releases/tag/v1.1.17", None

    with patch("ventoy_iso_check.ventoy_info.fetch_latest_ventoy", fake_latest):
        st = check_ventoy(tmp_path, online=True)
    assert st.local_version == "1.0.0"
    assert st.latest_version == "1.1.17"
    assert st.status == "OUTDATED"


def test_check_ventoy_ok(tmp_path: Path):
    vdir = tmp_path / "ventoy"
    vdir.mkdir()
    (vdir / "version").write_text("1.1.17\n", encoding="utf-8")

    with patch(
        "ventoy_iso_check.ventoy_info.fetch_latest_ventoy",
        lambda: ("1.1.17", "https://example.com", None),
    ):
        st = check_ventoy(tmp_path, online=True)
    assert st.status == "OK"
