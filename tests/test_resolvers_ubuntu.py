from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from ventoy_iso_check.models import CatalogEntry
from ventoy_iso_check.policy import UpgradePolicy
from ventoy_iso_check.resolvers import resolve_ubuntu
from ventoy_iso_check.version_cmp import is_outdated


def _fake_client(meta_text: str):
    """Context-manager fake of httpx.Client with get/head."""

    class FakeResp:
        def __init__(self, text: str = "", status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "err", request=MagicMock(), response=MagicMock()
                )

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url: str):
            if "meta-release" in url:
                return FakeResp(meta_text)
            return FakeResp("", 404)

        def head(self, url: str):
            return FakeResp("", 200)

    return FakeClient


def test_ubuntu_policies(sample_meta_release):
    server = CatalogEntry(
        id="ubuntu-live-server",
        label="server",
        patterns=[],
        managed_by="sisou",
        resolver="ubuntu",
        edition="live-server",
    )
    with patch(
        "ventoy_iso_check.resolvers._client",
        _fake_client(sample_meta_release),
    ):
        r_same = resolve_ubuntu(
            server,
            "24.04.4",
            policy=UpgradePolicy.SAME_SERIES,
            hint_newer=True,
        )
        assert r_same.latest_version == "24.04.4"
        assert is_outdated("24.04.4", r_same.latest_version) is False
        assert r_same.note and "26.04" in (r_same.note or "")

        r_lts = resolve_ubuntu(
            server,
            "24.04.4",
            policy=UpgradePolicy.LATEST_LTS,
        )
        assert r_lts.latest_version == "26.04"
        assert is_outdated("24.04.4", r_lts.latest_version) is True

        r_ok = resolve_ubuntu(
            server,
            "26.04",
            policy=UpgradePolicy.LATEST_LTS,
        )
        assert r_ok.latest_version == "26.04"
        assert is_outdated("26.04", r_ok.latest_version) is False
