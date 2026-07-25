from __future__ import annotations

from ventoy_iso_check.models import IsoItem, Status


def filter_items(
    items: list[IsoItem],
    *,
    only_outdated: bool = False,
    only_stale: bool = False,
    only_actionable: bool = False,
    stale_days: int | None = 180,
) -> list[IsoItem]:
    """Post-process filters (apply after run_check).

    - only_outdated: status == OUTDATED
    - only_stale: age_days >= stale_days
    - only_actionable: OUTDATED | ERROR | (stale if only_stale or always include stale
      when only_actionable — plan says OUTDATED | ERROR | stale if requested)

    Combinable: if several flags are set, an item must match **any** selected
    filter (OR), so you still see everything actionable.
    """
    if not (only_outdated or only_stale or only_actionable):
        return items

    def is_stale(it: IsoItem) -> bool:
        if stale_days is None or it.age_days is None:
            return False
        return it.age_days >= stale_days

    out: list[IsoItem] = []
    for it in items:
        match = False
        if only_outdated and it.status == Status.OUTDATED:
            match = True
        if only_stale and is_stale(it):
            match = True
        if only_actionable:
            if it.status in (Status.OUTDATED, Status.ERROR):
                match = True
            # actionable also includes stale files (old on disk) when age known
            if is_stale(it):
                match = True
        if match:
            out.append(it)
    return out
