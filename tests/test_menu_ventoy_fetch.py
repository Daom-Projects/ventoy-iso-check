"""Menu helpers and Ventoy package download (mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ventoy_iso_check.menu import run_menu
from ventoy_iso_check.ventoy_info import (
    _extract_archive,
    _pick_asset,
    download_ventoy_release,
)


def test_pick_asset_linux_windows():
    assets = [
        {
            "name": "ventoy-1.1.17-linux.tar.gz",
            "browser_download_url": "https://example.com/linux.tgz",
        },
        {
            "name": "ventoy-1.1.17-windows.zip",
            "browser_download_url": "https://example.com/win.zip",
        },
        {"name": "SHA256SUMS", "browser_download_url": "https://example.com/sum"},
    ]
    assert _pick_asset(assets, "linux")[0].endswith("linux.tar.gz")
    assert _pick_asset(assets, "windows")[0].endswith("windows.zip")


def test_extract_tar_gz(tmp_path: Path):
    import tarfile

    inner = tmp_path / "build"
    vdir = inner / "ventoy-1.1.17" / "ventoy"
    vdir.mkdir(parents=True)
    (vdir / "version").write_text("1.1.17\n", encoding="utf-8")
    archive = tmp_path / "ventoy-1.1.17-linux.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(inner / "ventoy-1.1.17", arcname="ventoy-1.1.17")
    dest = tmp_path / "out"
    dest.mkdir()
    extracted = _extract_archive(archive, dest)
    assert extracted.is_dir()
    assert (extracted / "ventoy" / "version").read_text(encoding="utf-8").startswith(
        "1.1.17"
    )


def test_download_ventoy_release_mocked(tmp_path: Path):
    import tarfile

    # Build a real tiny archive for extract step
    vroot = tmp_path / "src" / "ventoy-9.9.9" / "ventoy"
    vroot.mkdir(parents=True)
    (vroot / "version").write_text("9.9.9\n", encoding="utf-8")
    archive_path = tmp_path / "pkg" / "ventoy-9.9.9-linux.tar.gz"
    archive_path.parent.mkdir()
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(vroot.parent, arcname="ventoy-9.9.9")

    fake_json = {
        "tag_name": "v9.9.9",
        "assets": [
            {
                "name": "ventoy-9.9.9-linux.tar.gz",
                "browser_download_url": "https://example.com/v.tgz",
            }
        ],
    }

    def fake_download(url, dest, console=None):
        dest.write_bytes(archive_path.read_bytes())

    with (
        patch(
            "ventoy_iso_check.ventoy_info._github_release_json",
            return_value=fake_json,
        ),
        patch(
            "ventoy_iso_check.ventoy_info._download_file",
            side_effect=fake_download,
        ),
    ):
        out = tmp_path / "Bootloaders"
        paths = download_ventoy_release(out, platforms=["linux"], keep_archive=True)
    assert any(p.exists() for p in paths)
    assert any("ventoy" in p.name.lower() for p in paths if p.is_dir())


def test_run_menu_non_tty():
    with patch("sys.stdin") as stdin, patch("sys.stdout") as stdout:
        stdin.isatty.return_value = False
        stdout.isatty.return_value = False
        code = run_menu(Path("/tmp"))
    assert code == 2
