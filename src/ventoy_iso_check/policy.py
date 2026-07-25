from __future__ import annotations

from enum import Enum


class UpgradePolicy(str, Enum):
    """How to choose the comparison target (latest_version) for an ISO."""

    LATEST = "latest"
    """Absolute newest published release/ISO."""

    LATEST_LTS = "latest-lts"
    """Newest LTS (Ubuntu) or newest stable major (Fedora/Mint when LTS N/A)."""

    SAME_SERIES = "same-series"
    """Only track point-releases within the local series/major."""

    @classmethod
    def parse(cls, value: str | None) -> UpgradePolicy:
        if not value:
            return cls.LATEST_LTS
        key = value.strip().lower().replace("_", "-")
        for p in cls:
            if p.value == key:
                return p
        raise ValueError(
            f"Política desconocida: {value!r}. "
            f"Usa: {', '.join(p.value for p in cls)}"
        )


# Resolvers that understand upgrade policy
POLICY_AWARE_RESOLVERS = frozenset(
    {
        "ubuntu",
        "ubuntu_budgie",
        "linuxmint",
        "fedora",
        "popos",
        "elementary",
    }
)


def pick_target(
    *,
    policy: UpgradePolicy,
    series_best: str | None,
    latest_lts: str | None,
    absolute_latest: str | None,
) -> str | None:
    """Select comparison target under the given policy."""
    if policy == UpgradePolicy.SAME_SERIES:
        return series_best or absolute_latest
    if policy == UpgradePolicy.LATEST_LTS:
        return latest_lts or absolute_latest or series_best
    # LATEST
    return absolute_latest or latest_lts or series_best


def hint_note(
    *,
    policy: UpgradePolicy,
    series_best: str | None,
    absolute_latest: str | None,
    latest_lts: str | None = None,
    enabled: bool = False,
) -> str | None:
    """Optional note when same-series hides a newer major/LTS."""
    if not enabled or policy != UpgradePolicy.SAME_SERIES:
        return None
    newer = absolute_latest or latest_lts
    if not newer or not series_best or newer == series_best:
        return None
    from packaging.version import InvalidVersion, Version

    try:
        if Version(str(newer).replace("-", ".")) <= Version(
            str(series_best).replace("-", ".")
        ):
            return None
    except InvalidVersion:
        if newer == series_best:
            return None
    label = latest_lts if latest_lts and latest_lts == newer else absolute_latest
    return (
        f"Serie local al día en {series_best}; hay release más nueva disponible: "
        f"{label} (ignorada por policy=same-series)"
    )
