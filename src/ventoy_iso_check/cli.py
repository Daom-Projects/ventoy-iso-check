from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ventoy_iso_check import __version__
from ventoy_iso_check.checker import run_check
from ventoy_iso_check.filters import filter_items
from ventoy_iso_check.paths import default_ventoy_root, project_root
from ventoy_iso_check.reporters import print_table, write_json, write_links_markdown
from ventoy_iso_check.sisou_bridge import default_sisou_toml, run_sisou

app = typer.Typer(
    name="ventoy-iso-check",
    help=(
        "Inventario y verificación de ISOs en un disco Ventoy. "
        "Por defecto solo reporta; usa `download` para actualizar con sisou. "
        "Raíz por defecto: $VENTOY_ROOT, luego /ventoy, luego /mnt/e."
    ),
    add_completion=False,
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()


def _setup_log(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )


def _root_arg() -> Path:
    return default_ventoy_root()


def _display_opts(
    *,
    show_urls: bool,
    no_dates: bool,
    stale_days: Optional[int],
    sort_by: str,
) -> dict:
    return {
        "show_urls": show_urls,
        "show_dates": not no_dates,
        "stale_days": stale_days,
        "sort_by": sort_by,
    }


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", help="Mostrar versión y salir."
    ),
) -> None:
    if version:
        console.print(f"ventoy-iso-check {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@app.command("scan")
def scan_cmd(
    root: Optional[Path] = typer.Argument(
        None,
        help="Raíz del volumen Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    catalog: Optional[Path] = typer.Option(
        None, "--catalog", "-c", help="Ruta a catalog.yaml"
    ),
    deep: bool = typer.Option(
        False, "--deep", help="Incluir árboles pesados (p. ej. MediCat)."
    ),
    json_out: Optional[Path] = typer.Option(
        None, "--json", help="Escribir inventario a JSON."
    ),
    no_dates: bool = typer.Option(
        False, "--no-dates", help="Ocultar columnas de fecha/edad del archivo."
    ),
    stale_days: Optional[int] = typer.Option(
        180,
        "--stale-days",
        help="Resaltar ISOs con mtime ≥ N días (default 180). 0 = desactivar.",
    ),
    only_stale: bool = typer.Option(
        False,
        "--only-stale",
        help="Mostrar solo ISOs con age ≥ --stale-days.",
    ),
    only_actionable: bool = typer.Option(
        False,
        "--only-actionable",
        help="Mostrar OUTDATED, ERROR y/o stale (según age).",
    ),
    sort_by: str = typer.Option(
        "path",
        "--sort",
        help="Orden: path | date | age | status",
    ),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Solo inventario local (sin red). Incluye fecha de archivo y edad."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    items = run_check(ventoy, catalog_path=catalog, deep=deep, online=False)
    sd = None if stale_days == 0 else stale_days
    items = filter_items(
        items,
        only_stale=only_stale,
        only_actionable=only_actionable,
        stale_days=sd,
    )
    if not items:
        console.print("[yellow]Ninguna ISO coincide con los filtros aplicados.[/yellow]")
    print_table(
        items,
        **_display_opts(
            show_urls=False, no_dates=no_dates, stale_days=sd, sort_by=sort_by
        ),
    )
    if json_out:
        write_json(items, json_out)
        console.print(f"JSON escrito en {json_out}")


@app.command("check")
def check_cmd(
    root: Optional[Path] = typer.Argument(
        None,
        help="Raíz del volumen Ventoy.",
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    catalog: Optional[Path] = typer.Option(None, "--catalog", "-c"),
    deep: bool = typer.Option(False, "--deep"),
    only: Optional[str] = typer.Option(
        None,
        "--only",
        help="Filtrar por id/etiqueta/nombre (coma-separado).",
    ),
    offline: bool = typer.Option(False, "--offline", help="No consultar red."),
    json_out: Optional[Path] = typer.Option(None, "--json"),
    show_urls: bool = typer.Option(
        False, "--urls", help="Mostrar columna de URL/página."
    ),
    no_dates: bool = typer.Option(
        False, "--no-dates", help="Ocultar columnas de fecha/edad del archivo."
    ),
    stale_days: Optional[int] = typer.Option(
        180,
        "--stale-days",
        help="Resaltar ISOs con mtime ≥ N días (default 180). 0 = desactivar.",
    ),
    only_outdated: bool = typer.Option(
        False,
        "--only-outdated",
        help="Mostrar solo ISOs con status OUTDATED.",
    ),
    only_stale: bool = typer.Option(
        False,
        "--only-stale",
        help="Mostrar solo ISOs con age ≥ --stale-days.",
    ),
    only_actionable: bool = typer.Option(
        False,
        "--only-actionable",
        help="Mostrar OUTDATED, ERROR y archivos stale.",
    ),
    sort_by: str = typer.Option(
        "path",
        "--sort",
        help="Orden: path | date | age | status",
    ),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Comparar ISOs locales con las últimas versiones conocidas (sin descargar)."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    only_set = {s.strip() for s in only.split(",")} if only else None
    items = run_check(
        ventoy,
        catalog_path=catalog,
        deep=deep,
        online=not offline,
        only=only_set,
    )
    sd = None if stale_days == 0 else stale_days
    items = filter_items(
        items,
        only_outdated=only_outdated,
        only_stale=only_stale,
        only_actionable=only_actionable,
        stale_days=sd,
    )
    if not items:
        console.print("[yellow]Ninguna ISO coincide con los filtros aplicados.[/yellow]")
    print_table(
        items,
        **_display_opts(
            show_urls=show_urls, no_dates=no_dates, stale_days=sd, sort_by=sort_by
        ),
    )
    if json_out:
        write_json(items, json_out)
        console.print(f"JSON escrito en {json_out}")


@app.command("links")
def links_cmd(
    root: Optional[Path] = typer.Argument(
        None,
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    output: Path = typer.Option(
        Path("links.md"), "--output", "-o", help="Markdown de salida."
    ),
    catalog: Optional[Path] = typer.Option(None, "--catalog", "-c"),
    only: Optional[str] = typer.Option(None, "--only"),
    deep: bool = typer.Option(False, "--deep"),
    no_dates: bool = typer.Option(False, "--no-dates"),
    stale_days: Optional[int] = typer.Option(180, "--stale-days"),
    only_outdated: bool = typer.Option(False, "--only-outdated"),
    only_stale: bool = typer.Option(False, "--only-stale"),
    only_actionable: bool = typer.Option(False, "--only-actionable"),
    sort_by: str = typer.Option("path", "--sort"),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Generar enlaces directos / páginas oficiales (Markdown)."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    only_set = {s.strip() for s in only.split(",")} if only else None
    items = run_check(
        ventoy, catalog_path=catalog, deep=deep, online=True, only=only_set
    )
    sd = None if stale_days == 0 else stale_days
    items = filter_items(
        items,
        only_outdated=only_outdated,
        only_stale=only_stale,
        only_actionable=only_actionable,
        stale_days=sd,
    )
    if not items:
        console.print("[yellow]Ninguna ISO coincide con los filtros aplicados.[/yellow]")
    print_table(
        items,
        **_display_opts(
            show_urls=True, no_dates=no_dates, stale_days=sd, sort_by=sort_by
        ),
    )
    write_links_markdown(items, output)
    console.print(f"[green]Enlaces escritos en[/green] {output.resolve()}")


@app.command("download")
def download_cmd(
    root: Optional[Path] = typer.Argument(
        None,
        help="Raíz Ventoy (reescribe directory en sisou.toml al vuelo).",
        exists=False,
        file_okay=False,
        dir_okay=True,
    ),
    sisou_config: Optional[Path] = typer.Option(
        None,
        "--sisou-config",
        help="Ruta a sisou.toml (default: el del proyecto).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mostrar el comando sisou sin ejecutarlo."
    ),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """Descargar/actualizar ISOs soportadas mediante SuperISOUpdater (sisou).

    Requiere red y espacio libre. En host: uv + Python 3.12. En Docker: sisou embebido.
    """
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    cfg = sisou_config or default_sisou_toml()
    console.print(
        f"[bold]Descarga con sisou[/bold]\n"
        f"  config plantilla: {cfg}\n"
        f"  ventoy root:      {ventoy}\n"
        f"  proyecto:         {project_root()}\n"
        f"  dry_run={dry_run}"
    )
    if not ventoy.is_dir() and not dry_run:
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    code = run_sisou(
        cfg,
        ventoy_root=ventoy if ventoy.is_dir() or dry_run else None,
        log_level=log_level,
        dry_run=dry_run,
    )
    raise typer.Exit(code)


if __name__ == "__main__":
    app()
