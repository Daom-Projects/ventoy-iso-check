from __future__ import annotations

from unittest.mock import patch

from ventoy_iso_check.checker import run_check
from ventoy_iso_check.models import Status
from ventoy_iso_check.resolvers import ResolveResult


def test_run_check_offline_statuses(tmp_iso_tree):
    items = run_check(tmp_iso_tree, online=False)
    by_name = {i.filename: i for i in items}
    assert by_name["ubuntu-26.04-desktop-amd64.iso"].status == Status.UNKNOWN
    assert by_name["unknown-distro-1.0.iso"].status == Status.UNSUPPORTED
    assert by_name["clonezilla-live-3.3.3-15-amd64.iso"].catalog_id == "clonezilla"


def test_run_check_parallel_resolve(tmp_iso_tree):
    calls: list[str] = []

    def fake_resolve(entry, local_version, **kwargs):
        calls.append(entry.id)
        pol = kwargs.get("policy", "latest-lts")
        pol_s = pol.value if hasattr(pol, "value") else str(pol)
        return ResolveResult(
            latest_version=local_version or "1.0",
            download_url=f"https://example.com/{entry.id}.iso",
            page="https://example.com/",
            note="mocked",
            policy=pol_s,
        )

    with patch("ventoy_iso_check.checker.resolve", side_effect=fake_resolve):
        items = run_check(
            tmp_iso_tree,
            online=True,
            max_workers=4,
        )
    # at least ubuntu + fedora + clonezilla resolved
    assert len(calls) >= 3
    ok_like = [i for i in items if i.status in (Status.OK, Status.OUTDATED, Status.UNKNOWN)]
    assert len(ok_like) >= 3
