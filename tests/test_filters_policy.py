from __future__ import annotations

from pathlib import Path

from ventoy_iso_check.filters import filter_items
from ventoy_iso_check.models import IsoItem, Status
from ventoy_iso_check.policy import UpgradePolicy, hint_note, pick_target


def _item(name: str, status: Status, age: float | None = None) -> IsoItem:
    return IsoItem(
        path=Path(name),
        relpath=name,
        size=1,
        filename=name,
        status=status,
        age_days=age,
    )


def test_filter_only_outdated():
    items = [
        _item("a.iso", Status.OUTDATED, 1),
        _item("b.iso", Status.OK, 1),
        _item("c.iso", Status.ERROR, 1),
    ]
    out = filter_items(items, only_outdated=True)
    assert [i.filename for i in out] == ["a.iso"]


def test_filter_only_stale_and_actionable():
    items = [
        _item("old.iso", Status.OK, 200),
        _item("new.iso", Status.OK, 5),
        _item("bad.iso", Status.ERROR, 5),
        _item("out.iso", Status.OUTDATED, 5),
    ]
    stale = filter_items(items, only_stale=True, stale_days=180)
    assert [i.filename for i in stale] == ["old.iso"]

    act = filter_items(items, only_actionable=True, stale_days=180)
    names = {i.filename for i in act}
    assert names == {"old.iso", "bad.iso", "out.iso"}


def test_policy_parse_and_pick_target():
    assert UpgradePolicy.parse("same-series") == UpgradePolicy.SAME_SERIES
    assert UpgradePolicy.parse("LATEST_LTS") == UpgradePolicy.LATEST_LTS

    assert (
        pick_target(
            policy=UpgradePolicy.SAME_SERIES,
            series_best="24.04.4",
            latest_lts="26.04",
            absolute_latest="26.04",
        )
        == "24.04.4"
    )
    assert (
        pick_target(
            policy=UpgradePolicy.LATEST_LTS,
            series_best="24.04.4",
            latest_lts="26.04",
            absolute_latest="25.10",
        )
        == "26.04"
    )
    assert (
        pick_target(
            policy=UpgradePolicy.LATEST,
            series_best="24.04.4",
            latest_lts="26.04",
            absolute_latest="25.10",
        )
        == "25.10"
    )


def test_hint_note_only_same_series():
    note = hint_note(
        policy=UpgradePolicy.SAME_SERIES,
        series_best="24.04.4",
        absolute_latest="26.04",
        latest_lts="26.04",
        enabled=True,
    )
    assert note is not None and "26.04" in note

    assert (
        hint_note(
            policy=UpgradePolicy.LATEST_LTS,
            series_best="24.04.4",
            absolute_latest="26.04",
            enabled=True,
        )
        is None
    )
