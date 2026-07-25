from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ventoy_iso_check.models import IsoItem, Status

console = Console()

STATUS_STYLE = {
    Status.OK: "green",
    Status.OUTDATED: "yellow",
    Status.UNKNOWN: "cyan",
    Status.MANUAL: "magenta",
    Status.UNSUPPORTED: "dim",
    Status.ERROR: "red",
}


def format_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _age_style(age_days: float | None, *, stale_days: int | None) -> str:
    if age_days is None:
        return "dim"
    if stale_days is not None and age_days >= stale_days:
        return "bold red"
    if age_days < 30:
        return "green"
    if age_days < 180:
        return "yellow"
    return "red"


def print_table(
    items: list[IsoItem],
    *,
    show_urls: bool = False,
    show_dates: bool = True,
    stale_days: int | None = 180,
    sort_by: str = "path",
) -> None:
    rows = list(items)
    if sort_by == "age":
        rows.sort(
            key=lambda i: (i.age_days is None, -(i.age_days or 0), i.relpath.lower())
        )
    elif sort_by == "date":
        rows.sort(
            key=lambda i: (
                i.mtime is None,
                -(i.mtime.timestamp() if i.mtime else 0),
                i.relpath.lower(),
            )
        )
    elif sort_by == "status":
        order = {
            Status.OUTDATED: 0,
            Status.ERROR: 1,
            Status.UNKNOWN: 2,
            Status.UNSUPPORTED: 3,
            Status.MANUAL: 4,
            Status.OK: 5,
        }
        rows.sort(key=lambda i: (order.get(i.status, 9), i.relpath.lower()))
    else:
        rows.sort(key=lambda i: i.relpath.lower())

    table = Table(
        title="Ventoy ISO check",
        show_lines=False,
        expand=True,
    )
    table.add_column("Rel path", overflow="fold", min_width=24)
    table.add_column("Label", style="bold")
    table.add_column("Local", justify="right")
    table.add_column("Latest", justify="right")
    table.add_column("Status", justify="center")
    if show_dates:
        table.add_column("File date", justify="center")
        table.add_column("Age", justify="right")
    table.add_column("Meta", justify="center")
    table.add_column("Size", justify="right")
    table.add_column("Managed", justify="center")
    if show_urls:
        table.add_column("URL / page", overflow="fold")

    stale_count = 0
    meta_count = 0
    bad_sha = 0
    for it in rows:
        style = STATUS_STYLE.get(it.status, "")
        status_text = Text(it.status.value, style=style)
        row: list = [
            it.relpath,
            it.label or "—",
            it.local_version or "—",
            it.latest_version or "—",
            status_text,
        ]
        if show_dates:
            age_style = _age_style(it.age_days, stale_days=stale_days)
            date_label = it.file_date_str()
            if it.date_source == "meta":
                date_label = f"{date_label}*"
            row.append(Text(date_label, style=age_style))
            row.append(Text(it.age_label(), style=age_style))
            if (
                stale_days is not None
                and it.age_days is not None
                and it.age_days >= stale_days
            ):
                stale_count += 1
        meta_txt = it.meta_label()
        if it.has_meta:
            meta_count += 1
        if it.checksum_ok is False:
            bad_sha += 1
            row.append(Text(meta_txt, style="bold red"))
        elif it.has_meta:
            row.append(Text(meta_txt, style="green"))
        else:
            row.append(Text(meta_txt, style="dim"))
        row.append(format_size(it.size))
        row.append(it.managed_by)
        if show_urls:
            link = it.download_url or it.page or it.note or "—"
            if len(link) > 64:
                link = link[:61] + "..."
            row.append(link)
        table.add_row(*row)

    console.print(table)

    counts: dict[str, int] = {}
    for it in items:
        counts[it.status.value] = counts.get(it.status.value, 0) + 1
    summary = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    extra = ""
    if show_dates and stale_days is not None:
        extra = f"  stale(≥{stale_days}d)={stale_count}"
    extra += f"  meta={meta_count}"
    if bad_sha:
        extra += f"  bad_sha={bad_sha}"
    console.print(f"[bold]Resumen:[/bold] total={len(items)}  {summary}{extra}")
    if show_dates:
        console.print(
            "[dim]File date: * = sidecar .meta.json (downloaded_at); "
            "si no, mtime/birthtime del FS. Meta: ✓ = sidecar presente.[/dim]"
        )


def write_json(items: list[IsoItem], path: Path) -> None:
    path.write_text(
        json.dumps([i.to_dict() for i in items], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_links_markdown(items: list[IsoItem], path: Path) -> None:
    lines = [
        "# Enlaces de descarga / páginas oficiales",
        "",
        "Generado por `ventoy-iso-check`.",
        "",
        "| Archivo | Local | Latest | Status | File date | Age | Enlace |",
        "|---------|-------|--------|--------|-----------|-----|--------|",
    ]
    for it in items:
        if it.status not in (
            Status.OUTDATED,
            Status.UNKNOWN,
            Status.MANUAL,
            Status.ERROR,
        ):
            if it.status == Status.OK and not it.download_url:
                continue
        link = it.download_url or it.page or ""
        note = f" ({it.note})" if it.note and not it.download_url else ""
        lines.append(
            f"| `{it.relpath}` | {it.local_version or '—'} | {it.latest_version or '—'} "
            f"| {it.status.value} | {it.file_date_str()} | {it.age_label()} "
            f"| {link}{note} |"
        )
    lines.extend(["", "## Todas las URLs detectadas", ""])
    for it in items:
        if it.download_url:
            lines.append(
                f"- **{it.label or it.filename}** "
                f"(`{it.local_version}` → `{it.latest_version}`, "
                f"{it.file_date_str()} / {it.age_label()}): {it.download_url}"
            )
        elif it.page:
            lines.append(
                f"- **{it.label or it.filename}** "
                f"({it.file_date_str()}): {it.page}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
