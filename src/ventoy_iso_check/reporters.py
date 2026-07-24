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
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def print_table(items: list[IsoItem], *, show_urls: bool = False) -> None:
    table = Table(
        title="Ventoy ISO check",
        show_lines=False,
        expand=True,
    )
    table.add_column("Rel path", overflow="fold", min_width=28)
    table.add_column("Label", style="bold")
    table.add_column("Local", justify="right")
    table.add_column("Latest", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Managed", justify="center")
    table.add_column("Size", justify="right")
    if show_urls:
        table.add_column("URL / page", overflow="fold")

    for it in items:
        style = STATUS_STYLE.get(it.status, "")
        status_text = Text(it.status.value, style=style)
        row = [
            it.relpath,
            it.label or "—",
            it.local_version or "—",
            it.latest_version or "—",
            status_text,
            it.managed_by,
            format_size(it.size),
        ]
        if show_urls:
            link = it.download_url or it.page or it.note or "—"
            if len(link) > 72:
                link = link[:69] + "..."
            row.append(link)
        table.add_row(*row)

    console.print(table)

    counts: dict[str, int] = {}
    for it in items:
        counts[it.status.value] = counts.get(it.status.value, 0) + 1
    summary = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    console.print(f"[bold]Resumen:[/bold] total={len(items)}  {summary}")


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
        "| Archivo | Local | Latest | Status | Enlace |",
        "|---------|-------|--------|--------|--------|",
    ]
    for it in items:
        if it.status not in (Status.OUTDATED, Status.UNKNOWN, Status.MANUAL, Status.ERROR):
            # still include outdated/manual primarily
            if it.status == Status.OK and not it.download_url:
                continue
        link = it.download_url or it.page or ""
        note = f" ({it.note})" if it.note and not it.download_url else ""
        lines.append(
            f"| `{it.relpath}` | {it.local_version or '—'} | {it.latest_version or '—'} "
            f"| {it.status.value} | {link}{note} |"
        )
    # also list all with any URL at the end
    lines.extend(["", "## Todas las URLs detectadas", ""])
    for it in items:
        if it.download_url:
            lines.append(f"- **{it.label or it.filename}** (`{it.local_version}` → `{it.latest_version}`): {it.download_url}")
        elif it.page:
            lines.append(f"- **{it.label or it.filename}** (página): {it.page}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
