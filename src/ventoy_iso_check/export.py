from __future__ import annotations

import csv
import html
from datetime import datetime, timezone
from pathlib import Path

from ventoy_iso_check import __version__
from ventoy_iso_check.models import IsoItem
from ventoy_iso_check.reporters import format_size


CSV_FIELDS = [
    "relpath",
    "label",
    "local_version",
    "latest_version",
    "status",
    "managed_by",
    "size",
    "size_human",
    "file_date",
    "age_label",
    "age_days",
    "date_source",
    "has_meta",
    "meta_sha256",
    "checksum_ok",
    "download_url",
    "page",
    "note",
    "catalog_id",
]


def write_csv(items: list[IsoItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for it in items:
            w.writerow(
                {
                    "relpath": it.relpath,
                    "label": it.label or "",
                    "local_version": it.local_version or "",
                    "latest_version": it.latest_version or "",
                    "status": it.status.value,
                    "managed_by": it.managed_by,
                    "size": it.size,
                    "size_human": format_size(it.size),
                    "file_date": it.file_date_str(),
                    "age_label": it.age_label(),
                    "age_days": f"{it.age_days:.2f}" if it.age_days is not None else "",
                    "date_source": it.date_source,
                    "has_meta": it.has_meta,
                    "meta_sha256": it.meta_sha256 or "",
                    "checksum_ok": ""
                    if it.checksum_ok is None
                    else ("true" if it.checksum_ok else "false"),
                    "download_url": it.download_url or "",
                    "page": it.page or "",
                    "note": it.note or "",
                    "catalog_id": it.catalog_id or "",
                }
            )


def write_html(
    items: list[IsoItem],
    path: Path,
    *,
    title: str = "Ventoy ISO report",
    ventoy_section: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    counts: dict[str, int] = {}
    for it in items:
        counts[it.status.value] = counts.get(it.status.value, 0) + 1
    summary = " · ".join(f"{k}={v}" for k, v in sorted(counts.items()))

    rows_html = []
    for it in items:
        status = it.status.value
        cls = f"st-{status.lower()}"
        url = it.download_url or it.page or ""
        url_cell = (
            f'<a href="{html.escape(url)}">{html.escape(url[:80])}</a>'
            if url
            else "—"
        )
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(it.relpath)}</td>"
            f"<td>{html.escape(it.label or '—')}</td>"
            f"<td>{html.escape(it.local_version or '—')}</td>"
            f"<td>{html.escape(it.latest_version or '—')}</td>"
            f'<td class="{cls}">{html.escape(status)}</td>'
            f"<td>{html.escape(it.file_date_str())}</td>"
            f"<td>{html.escape(it.age_label())}</td>"
            f"<td>{html.escape(it.meta_label())}</td>"
            f"<td>{html.escape(format_size(it.size))}</td>"
            f"<td>{html.escape(it.managed_by)}</td>"
            f"<td>{url_cell}</td>"
            "</tr>"
        )

    ventoy_block = ""
    if ventoy_section:
        ventoy_block = f"<section class='ventoy'><h2>Ventoy bootloader</h2>{ventoy_section}</section>"

    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>
  :root {{ font-family: system-ui, sans-serif; color: #1a1a1a; }}
  body {{ margin: 1.5rem; background: #f6f7f9; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  .meta {{ color: #555; margin-bottom: 1rem; font-size: 0.9rem; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); font-size: 0.85rem; }}
  th, td {{ border-bottom: 1px solid #e5e7eb; padding: 0.45rem 0.55rem;
            text-align: left; vertical-align: top; }}
  th {{ background: #111827; color: #fff; position: sticky; top: 0; }}
  tr:hover td {{ background: #f3f4f6; }}
  .st-ok {{ color: #047857; font-weight: 600; }}
  .st-outdated {{ color: #b45309; font-weight: 600; }}
  .st-error {{ color: #b91c1c; font-weight: 600; }}
  .st-manual {{ color: #6d28d9; }}
  .st-unknown {{ color: #0369a1; }}
  .st-unsupported {{ color: #6b7280; }}
  .ventoy {{ margin: 1rem 0; padding: 0.75rem 1rem; background: #fff;
             border-left: 4px solid #2563eb; }}
  a {{ color: #1d4ed8; }}
</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="meta">Generado por ventoy-iso-check {html.escape(__version__)}
    · {html.escape(now)} · total={len(items)} · {html.escape(summary)}</p>
  {ventoy_block}
  <table>
    <thead>
      <tr>
        <th>Path</th><th>Label</th><th>Local</th><th>Latest</th><th>Status</th>
        <th>File date</th><th>Age</th><th>Meta</th><th>Size</th><th>Managed</th><th>URL</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")
