"""Menú interactivo de consola (Rich + prompts).

Complementa la CLI por flags/subcomandos de Typer (Click).
Se lanza con `ventoy-iso-check menu` o sin argumentos en un TTY.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from ventoy_iso_check import __version__
from ventoy_iso_check.bootloaders import check_bootloaders, format_bootloaders_console
from ventoy_iso_check.cache import ResolveCache, default_cache_file
from ventoy_iso_check.checker import run_check
from ventoy_iso_check.disk import SpaceVerdict, check_download_space
from ventoy_iso_check.export import write_csv, write_html
from ventoy_iso_check.filters import filter_items
from ventoy_iso_check.meta import seal_tree
from ventoy_iso_check.paths import default_ventoy_root
from ventoy_iso_check.policy import UpgradePolicy
from ventoy_iso_check.reporters import print_table, write_json, write_links_markdown
from ventoy_iso_check.sisou_bridge import default_sisou_toml, run_sisou
from ventoy_iso_check.suggest import format_suggestions, suggest_unsupported
from ventoy_iso_check.ventoy_info import (
    check_ventoy,
    download_ventoy_release,
    format_ventoy_console,
)

console = Console()


def _banner(root: Path) -> None:
    title = Text.assemble(
        ("ventoy-iso-check", "bold cyan"),
        (f"  v{__version__}", "dim"),
    )
    body = (
        f"[bold]Raíz Ventoy:[/bold] {root}\n"
        "[dim]CLI por flags sigue disponible "
        "(scan, check, export, …). Este menú cubre lo mismo de forma guiada.[/dim]"
    )
    console.print(Panel(body, title=title, border_style="cyan", expand=False))


def _menu_table() -> None:
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("key", style="bold yellow", width=4)
    t.add_column("action")
    rows = [
        ("1", "Escanear ISOs (solo local, sin red)"),
        ("2", "Comprobar versiones (red + cache)"),
        ("3", "Solo desactualizadas / accionables"),
        ("4", "Generar enlaces Markdown"),
        ("5", "Exportar informe (CSV / HTML / JSON)"),
        ("6", "Estado del bootloader Ventoy"),
        ("7", "Bootloaders/ (Ventoy + Rufus + Etcher)"),
        ("8", "Descargar paquete Ventoy latest → Bootloaders/"),
        ("9", "Sugerir entradas de catálogo (UNSUPPORTED)"),
        ("10", "Descargar/actualizar ISOs con sisou"),
        ("11", "Meta: sellar sidecars .meta.json"),
        ("12", "Meta: verificar checksums"),
        ("13", "Cambiar raíz del volumen Ventoy"),
        ("14", "Ayuda rápida (comandos CLI)"),
        ("0", "Salir"),
    ]
    for k, a in rows:
        t.add_row(k, a)
    console.print(Panel(t, title="[bold]Menú principal[/bold]", border_style="blue"))


def _ask_root(current: Path) -> Path:
    raw = Prompt.ask(
        "Ruta raíz Ventoy",
        default=str(current),
    ).strip()
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        console.print(f"[red]No es un directorio:[/red] {p}")
        return current
    return p


def _ensure_root(root: Path) -> bool:
    if root.is_dir():
        return True
    console.print(f"[red]No existe o no está montado:[/red] {root}")
    console.print(
        "[dim]En WSL: monta E:\\ o exporta VENTOY_ROOT. "
        "En Docker: -v /ruta:/ventoy[/dim]"
    )
    return False


def _do_scan(root: Path) -> None:
    if not _ensure_root(root):
        return
    deep = Confirm.ask("¿Incluir árboles pesados (--deep)?", default=False)
    items = run_check(root, online=False, deep=deep)
    print_table(items, show_dates=True, stale_days=180, sort_by="age")
    console.print(f"[green]Total:[/green] {len(items)} ISO(s)")


def _do_check(root: Path, *, only_outdated: bool = False, actionable: bool = False) -> None:
    if not _ensure_root(root):
        return
    show_urls = Confirm.ask("¿Mostrar URLs de descarga?", default=True)
    policy_raw = Prompt.ask(
        "Política de upgrade",
        choices=["latest-lts", "latest", "same-series"],
        default="latest-lts",
    )
    cache = ResolveCache(path=default_cache_file(), ttl_hours=12.0, enabled=True)
    items = run_check(
        root,
        online=True,
        policy=UpgradePolicy.parse(policy_raw),
        cache=cache,
        max_workers=8,
    )
    if only_outdated:
        items = filter_items(items, only_outdated=True)
    if actionable:
        items = filter_items(items, only_actionable=True, stale_days=180)
    print_table(
        items,
        show_urls=show_urls,
        show_dates=True,
        stale_days=180,
        sort_by="status",
    )
    console.print(cache.stats_line())
    if not items and (only_outdated or actionable):
        console.print("[green]Ninguna ISO en ese filtro.[/green]")


def _do_links(root: Path) -> None:
    if not _ensure_root(root):
        return
    default = Path.home() / "ventoy-links.md"
    out = Path(Prompt.ask("Archivo de salida", default=str(default))).expanduser()
    items = run_check(root, online=True, cache=ResolveCache(path=default_cache_file()))
    write_links_markdown(items, out)
    console.print(f"[green]Enlaces →[/green] {out.resolve()}")


def _do_export(root: Path) -> None:
    if not _ensure_root(root):
        return
    fmt = Prompt.ask("Formato", choices=["csv", "html", "json"], default="html")
    default = Path.home() / f"ventoy-report.{fmt}"
    out = Path(Prompt.ask("Archivo de salida", default=str(default))).expanduser()
    only_od = Confirm.ask("¿Solo OUTDATED?", default=False)
    items = run_check(
        root,
        online=True,
        cache=ResolveCache(path=default_cache_file()),
        max_workers=8,
    )
    if only_od:
        items = filter_items(items, only_outdated=True)
    st = check_ventoy(root, online=True)
    if fmt == "csv":
        write_csv(items, out)
    elif fmt == "html":
        write_html(items, out, ventoy_section=format_ventoy_console(st).replace("\n", "<br/>"))
    else:
        write_json(items, out, extra={"ventoy": st.to_dict()})
    console.print(f"[green]Exportado[/green] {len(items)} → {out.resolve()}")
    console.print(format_ventoy_console(st))


def _do_ventoy_status(root: Path) -> None:
    if not _ensure_root(root):
        return
    st = check_ventoy(root, online=True)
    console.print(format_ventoy_console(st))
    if st.status == "OUTDATED":
        console.print(
            "\n[yellow]Tip:[/yellow] opción [bold]8[/bold] descarga el paquete "
            "oficial a Bootloaders/. Luego actualiza el bootloader con "
            "[bold]Ventoy2Disk[/bold] (Windows) o el script Linux del paquete "
            "(no se modifica el MBR/ESP desde aquí)."
        )


def _do_bootloaders(root: Path) -> None:
    if not _ensure_root(root):
        return
    tools = check_bootloaders(root, online=True)
    console.print(format_bootloaders_console(tools))


def _do_ventoy_fetch(root: Path) -> None:
    if not _ensure_root(root):
        return
    platform = Prompt.ask(
        "Paquete a descargar",
        choices=["linux", "windows", "both"],
        default="both",
    )
    dest = root / "Bootloaders"
    console.print(f"Destino: [cyan]{dest}[/cyan]")
    if not Confirm.ask("¿Descargar e extraer el release latest de Ventoy?", default=True):
        return
    try:
        paths = download_ventoy_release(
            dest,
            platforms=["linux", "windows"] if platform == "both" else [platform],
            console=console,
        )
        for p in paths:
            console.print(f"[green]Listo:[/green] {p}")
        console.print(
            Panel(
                "El paquete está en Bootloaders/, pero el [bold]bootloader instalado[/bold] "
                "en el USB se actualiza con Ventoy2Disk.exe (Windows) o "
                "Ventoy2Disk.sh (Linux) del paquete extraído.\n"
                "No se toca el MBR/ESP desde ventoy-iso-check.",
                title="Importante",
                border_style="yellow",
            )
        )
    except Exception as e:
        console.print(f"[red]Error descargando Ventoy:[/red] {e}")


def _do_suggest(root: Path) -> None:
    if not _ensure_root(root):
        return
    suggestions = suggest_unsupported(root)
    text = format_suggestions(suggestions)
    console.print(text)
    if suggestions and Confirm.ask("¿Guardar a archivo?", default=False):
        out = Path(
            Prompt.ask("Ruta", default=str(Path.home() / "catalog-suggestions.yaml"))
        ).expanduser()
        out.write_text(text, encoding="utf-8")
        console.print(f"[green]→[/green] {out.resolve()}")


def _do_download(root: Path) -> None:
    if not _ensure_root(root):
        return
    dry = Confirm.ask("¿Solo dry-run (no descargar)?", default=True)
    _space, verdict, msg = check_download_space(root, warn_gib=8.0, abort_gib=2.0, force=False)
    if verdict == SpaceVerdict.ABORT:
        console.print(f"[red]{msg}[/red]")
        return
    if verdict == SpaceVerdict.WARN:
        console.print(f"[yellow]{msg}[/yellow]")
        if not Confirm.ask("¿Continuar?", default=False):
            return
    else:
        console.print(f"[green]{msg}[/green]")
    if not dry and not Confirm.ask(
        "[bold red]Esto puede descargar varios GiB. ¿Seguro?[/bold red]",
        default=False,
    ):
        return
    code = run_sisou(default_sisou_toml(), ventoy_root=root, dry_run=dry)
    console.print(f"sisou exit={code}")


def _do_meta_seal(root: Path) -> None:
    if not _ensure_root(root):
        return
    compute_hash = Confirm.ask("¿Calcular SHA-256? (lento en USB)", default=False)
    written = seal_tree(root, only_missing=True, compute_hash=compute_hash)
    console.print(f"[green]Sidecars escritos:[/green] {len(written)}")
    for p in written[:15]:
        console.print(f"  {p}")
    if len(written) > 15:
        console.print(f"  … y {len(written) - 15} más")


def _do_meta_verify(root: Path) -> None:
    if not _ensure_root(root):
        return
    items = run_check(root, online=False, verify_checksum=True)
    with_hash = [i for i in items if i.meta_sha256]
    if not with_hash:
        console.print(
            "[yellow]Ninguna ISO con sha256 en sidecar. Usa la opción 10 con hash.[/yellow]"
        )
        return
    bad = [i for i in with_hash if i.checksum_ok is False]
    ok_n = sum(1 for i in with_hash if i.checksum_ok is True)
    console.print(f"Verificados: {len(with_hash)}  OK={ok_n}  FAIL={len(bad)}")
    print_table(with_hash, show_dates=True)
    for i in bad:
        console.print(f"[red]FAIL[/red] {i.relpath}: {i.note}")


def _do_help() -> None:
    console.print(
        Panel(
            "[bold]Comandos CLI (flags)[/bold]\n\n"
            "  ventoy-iso-check scan [ROOT] --sort age\n"
            "  ventoy-iso-check check [ROOT] --only-outdated --urls\n"
            "  ventoy-iso-check links [ROOT] -o links.md\n"
            "  ventoy-iso-check export [ROOT] -o report.html\n"
            "  ventoy-iso-check ventoy [ROOT]\n"
            "  ventoy-iso-check ventoy [ROOT] --fetch --platform both\n"
            "  ventoy-iso-check bootloaders [ROOT]\n"
            "  ventoy-iso-check suggest [ROOT]\n"
            "  ventoy-iso-check download [ROOT] --dry-run\n"
            "  ventoy-iso-check meta seal|verify [ROOT]\n"
            "  ventoy-iso-check menu [ROOT]\n\n"
            "[dim]Ayuda detallada: ventoy-iso-check --help / COMMAND --help[/dim]",
            title="CLI",
            border_style="green",
        )
    )


def run_menu(root: Path | None = None) -> int:
    """Bucle principal del menú. Devuelve código de salida."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        console.print(
            "[yellow]No hay TTY interactivo.[/yellow] "
            "Usa subcomandos: [bold]scan[/bold], [bold]check[/bold], … "
            "o [bold]--help[/bold]."
        )
        return 2

    current = (root or default_ventoy_root()).resolve()

    while True:
        console.print()
        _banner(current)
        _menu_table()
        choice = Prompt.ask("Elige opción", default="0").strip()

        if choice in ("0", "q", "salir", "exit"):
            console.print("[dim]Hasta luego.[/dim]")
            return 0
        if choice == "1":
            _do_scan(current)
        elif choice == "2":
            _do_check(current)
        elif choice == "3":
            mode = Prompt.ask(
                "Filtro",
                choices=["outdated", "actionable"],
                default="outdated",
            )
            _do_check(
                current,
                only_outdated=mode == "outdated",
                actionable=mode == "actionable",
            )
        elif choice == "4":
            _do_links(current)
        elif choice == "5":
            _do_export(current)
        elif choice == "6":
            _do_ventoy_status(current)
        elif choice == "7":
            _do_bootloaders(current)
        elif choice == "8":
            _do_ventoy_fetch(current)
        elif choice == "9":
            _do_suggest(current)
        elif choice == "10":
            _do_download(current)
        elif choice == "11":
            _do_meta_seal(current)
        elif choice == "12":
            _do_meta_verify(current)
        elif choice == "13":
            current = _ask_root(current)
        elif choice == "14":
            _do_help()
        else:
            console.print(f"[yellow]Opción no válida:[/yellow] {choice}")
            continue

        console.print()
        if not Confirm.ask("¿Volver al menú?", default=True):
            console.print("[dim]Hasta luego.[/dim]")
            return 0
