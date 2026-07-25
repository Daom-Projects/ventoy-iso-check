from __future__ import annotations

import logging
from datetime import UTC
from pathlib import Path

import typer
from rich.console import Console

from ventoy_iso_check import __version__
from ventoy_iso_check.bootloaders import check_bootloaders, format_bootloaders_console
from ventoy_iso_check.cache import ResolveCache, default_cache_file
from ventoy_iso_check.checker import DEFAULT_RESOLVE_WORKERS, run_check
from ventoy_iso_check.disk import SpaceVerdict, check_download_space
from ventoy_iso_check.export import write_csv, write_html
from ventoy_iso_check.filters import filter_items
from ventoy_iso_check.menu import run_menu
from ventoy_iso_check.meta import seal_tree, write_meta_for_iso
from ventoy_iso_check.paths import default_ventoy_root, project_root
from ventoy_iso_check.policy import UpgradePolicy
from ventoy_iso_check.reporters import print_table, write_json, write_links_markdown
from ventoy_iso_check.sisou_bridge import default_sisou_toml, run_sisou
from ventoy_iso_check.suggest import format_suggestions, suggest_unsupported
from ventoy_iso_check.ventoy_info import (
    check_ventoy,
    download_ventoy_release,
    format_ventoy_console,
    format_ventoy_html,
)

app = typer.Typer(
    name="ventoy-iso-check",
    help=(
        "Inventario y verificación de ISOs en un disco Ventoy. "
        "Sin argumentos en un TTY abre el menú interactivo (Rich). "
        "Todos los subcomandos y flags siguen disponibles. "
        "Raíz por defecto: $VENTOY_ROOT, luego /ventoy, luego /mnt/e."
    ),
    add_completion=False,
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
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
    stale_days: int | None,
    sort_by: str,
) -> dict:
    return {
        "show_urls": show_urls,
        "show_dates": not no_dates,
        "stale_days": stale_days,
        "sort_by": sort_by,
    }


def _build_cache(
    *,
    no_cache: bool,
    refresh: bool,
    cache_dir: Path | None,
    ttl_hours: float,
) -> ResolveCache | None:
    if no_cache:
        return None
    path = default_cache_file(cache_dir) if cache_dir else default_cache_file()
    return ResolveCache(
        path=path,
        ttl_hours=ttl_hours,
        enabled=True,
        refresh=refresh,
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", help="Mostrar versión y salir."
    ),
    menu: bool = typer.Option(
        False,
        "--menu",
        "-m",
        help="Abrir menú interactivo (también es el default sin subcomando en TTY).",
    ),
) -> None:
    if version:
        console.print(f"ventoy-iso-check {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is not None:
        return
    # Sin subcomando: menú si hay consola (o se forzó); si no, ayuda.
    import os

    from ventoy_iso_check.menu import _is_interactive

    force = os.environ.get("VENTOY_ISO_CHECK_INTERACTIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "on",
    )
    if menu or force or _is_interactive():
        code = run_menu()
        raise typer.Exit(code)
    console.print(ctx.get_help())
    raise typer.Exit(0)


@app.command("menu")
def menu_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz del volumen Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
    ),
) -> None:
    """Menú interactivo (Rich): scan, check, export, Ventoy, meta, sisou, …"""
    code = run_menu(root)
    raise typer.Exit(code)


@app.command("scan")
def scan_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz del volumen Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    catalog: Path | None = typer.Option(
        None, "--catalog", "-c", help="Ruta a catalog.yaml"
    ),
    deep: bool = typer.Option(
        False, "--deep", help="Incluir árboles pesados (p. ej. MediCat)."
    ),
    json_out: Path | None = typer.Option(
        None, "--json", help="Escribir inventario a JSON."
    ),
    no_dates: bool = typer.Option(
        False, "--no-dates", help="Ocultar columnas de fecha/edad del archivo."
    ),
    stale_days: int | None = typer.Option(
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
    verify_checksum: bool = typer.Option(
        False,
        "--verify-checksum",
        help="Verificar SHA-256 de sidecars (lento).",
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
    items = run_check(
        ventoy,
        catalog_path=catalog,
        deep=deep,
        online=False,
        verify_checksum=verify_checksum,
    )
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
    root: Path | None = typer.Argument(
        None,
        help="Raíz del volumen Ventoy.",
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    catalog: Path | None = typer.Option(None, "--catalog", "-c"),
    deep: bool = typer.Option(False, "--deep"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Filtrar por id/etiqueta/nombre (coma-separado).",
    ),
    offline: bool = typer.Option(False, "--offline", help="No consultar red."),
    json_out: Path | None = typer.Option(None, "--json"),
    show_urls: bool = typer.Option(
        False, "--urls", help="Mostrar columna de URL/página."
    ),
    no_dates: bool = typer.Option(
        False, "--no-dates", help="Ocultar columnas de fecha/edad del archivo."
    ),
    stale_days: int | None = typer.Option(
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
    no_cache: bool = typer.Option(
        False, "--no-cache", help="No usar cache de latest (ni leer ni escribir)."
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Ignorar cache al leer y volver a consultar la red (sí escribe).",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Directorio de cache (default: ~/.cache/ventoy-iso-check).",
    ),
    ttl_hours: float = typer.Option(
        12.0,
        "--ttl-hours",
        help="TTL del cache de latest en horas (default 12).",
    ),
    verify_checksum: bool = typer.Option(
        False,
        "--verify-checksum",
        help="Verificar SHA-256 de sidecars .meta.json (lento en USB).",
    ),
    policy: str = typer.Option(
        "latest-lts",
        "--policy",
        help="Upgrade policy: latest | latest-lts | same-series (default: latest-lts).",
    ),
    hint_newer: bool = typer.Option(
        False,
        "--hint-newer-lts",
        help="Con policy=same-series, anotar si hay LTS/release más nueva disponible.",
    ),
    workers: int = typer.Option(
        DEFAULT_RESOLVE_WORKERS,
        "--workers",
        help="Hilos para resolvers HTTP en paralelo (default 8).",
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
    try:
        pol = UpgradePolicy.parse(policy)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    only_set = {s.strip() for s in only.split(",")} if only else None
    cache = None
    if not offline:
        cache = _build_cache(
            no_cache=no_cache,
            refresh=refresh,
            cache_dir=cache_dir,
            ttl_hours=ttl_hours,
        )
    items = run_check(
        ventoy,
        catalog_path=catalog,
        deep=deep,
        online=not offline,
        only=only_set,
        cache=cache,
        verify_checksum=verify_checksum,
        policy=pol,
        hint_newer=hint_newer,
        max_workers=workers,
    )
    if cache is not None:
        console.print(f"[dim]{cache.stats_line()}[/dim]")
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
    root: Path | None = typer.Argument(
        None,
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    output: Path = typer.Option(
        Path("links.md"), "--output", "-o", help="Markdown de salida."
    ),
    catalog: Path | None = typer.Option(None, "--catalog", "-c"),
    only: str | None = typer.Option(None, "--only"),
    deep: bool = typer.Option(False, "--deep"),
    no_dates: bool = typer.Option(False, "--no-dates"),
    stale_days: int | None = typer.Option(180, "--stale-days"),
    only_outdated: bool = typer.Option(False, "--only-outdated"),
    only_stale: bool = typer.Option(False, "--only-stale"),
    only_actionable: bool = typer.Option(False, "--only-actionable"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
    cache_dir: Path | None = typer.Option(None, "--cache-dir"),
    ttl_hours: float = typer.Option(12.0, "--ttl-hours"),
    policy: str = typer.Option(
        "latest-lts",
        "--policy",
        help="Upgrade policy: latest | latest-lts | same-series.",
    ),
    hint_newer: bool = typer.Option(False, "--hint-newer-lts"),
    workers: int = typer.Option(DEFAULT_RESOLVE_WORKERS, "--workers"),
    sort_by: str = typer.Option("path", "--sort"),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Generar enlaces directos / páginas oficiales (Markdown)."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    try:
        pol = UpgradePolicy.parse(policy)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    only_set = {s.strip() for s in only.split(",")} if only else None
    cache = _build_cache(
        no_cache=no_cache,
        refresh=refresh,
        cache_dir=cache_dir,
        ttl_hours=ttl_hours,
    )
    items = run_check(
        ventoy,
        catalog_path=catalog,
        deep=deep,
        online=True,
        only=only_set,
        cache=cache,
        policy=pol,
        hint_newer=hint_newer,
        max_workers=workers,
    )
    if cache is not None:
        console.print(f"[dim]{cache.stats_line()}[/dim]")
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


@app.command("export")
def export_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Archivo de salida (.csv, .html o .json).",
    ),
    fmt: str | None = typer.Option(
        None,
        "--format",
        "-f",
        help="csv | html | json (default: por extensión de -o).",
    ),
    offline: bool = typer.Option(False, "--offline"),
    only: str | None = typer.Option(None, "--only"),
    only_outdated: bool = typer.Option(False, "--only-outdated"),
    only_stale: bool = typer.Option(False, "--only-stale"),
    only_actionable: bool = typer.Option(False, "--only-actionable"),
    stale_days: int | None = typer.Option(180, "--stale-days"),
    policy: str = typer.Option("latest-lts", "--policy"),
    include_ventoy: bool = typer.Option(
        True,
        "--ventoy/--no-ventoy",
        help="Incluir sección Ventoy bootloader (html/json).",
    ),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
    workers: int = typer.Option(DEFAULT_RESOLVE_WORKERS, "--workers"),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Exportar inventario a CSV, HTML o JSON."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)

    fmt_l = (fmt or output.suffix.lstrip(".")).lower()
    if fmt_l not in ("csv", "html", "json"):
        console.print("[red]Formato no soportado. Usa csv, html o json.[/red]")
        raise typer.Exit(2)

    try:
        pol = UpgradePolicy.parse(policy)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    only_set = {s.strip() for s in only.split(",")} if only else None
    cache = None
    if not offline:
        cache = _build_cache(
            no_cache=no_cache,
            refresh=refresh,
            cache_dir=None,
            ttl_hours=12.0,
        )
    items = run_check(
        ventoy,
        online=not offline,
        only=only_set,
        cache=cache,
        policy=pol,
        max_workers=workers,
    )
    sd = None if stale_days == 0 else stale_days
    items = filter_items(
        items,
        only_outdated=only_outdated,
        only_stale=only_stale,
        only_actionable=only_actionable,
        stale_days=sd,
    )

    vstatus = None
    if include_ventoy:
        vstatus = check_ventoy(ventoy, online=not offline)

    if fmt_l == "csv":
        write_csv(items, output)
    elif fmt_l == "html":
        vhtml = format_ventoy_html(vstatus) if vstatus else None
        write_html(items, output, ventoy_section=vhtml)
    else:
        extra = {"ventoy": vstatus.to_dict()} if vstatus else None
        write_json(items, output, extra=extra)

    console.print(
        f"[green]Exportado[/green] {len(items)} ISO(s) → {output.resolve()} ({fmt_l})"
    )
    if vstatus:
        console.print(format_ventoy_console(vstatus))


@app.command("ventoy")
def ventoy_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
    ),
    offline: bool = typer.Option(False, "--offline"),
    json_out: Path | None = typer.Option(None, "--json"),
    fetch: bool = typer.Option(
        False,
        "--fetch",
        help="Descargar e extraer el release latest a Bootloaders/ (no instala MBR/ESP).",
    ),
    platform: str = typer.Option(
        "both",
        "--platform",
        "-p",
        help="Con --fetch: linux | windows | both",
    ),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Con --fetch: destino (default ROOT/Bootloaders).",
    ),
    keep_archive: bool = typer.Option(
        True,
        "--keep-archive/--no-keep-archive",
        help="Con --fetch: conservar .tar.gz / .zip.",
    ),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Bootloader Ventoy: estado local vs GitHub; opcionalmente --fetch del paquete."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir() and not fetch:
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)

    if fetch:
        out = (dest or (ventoy / "Bootloaders")).resolve()
        plat = platform.lower().strip()
        if plat == "both":
            platforms = ["linux", "windows"]
        elif plat in ("linux", "windows"):
            platforms = [plat]
        else:
            console.print("[red]--platform debe ser linux, windows o both[/red]")
            raise typer.Exit(2)
        console.print(
            f"[bold]Ventoy fetch[/bold]\n"
            f"  destino:     {out}\n"
            f"  plataformas: {', '.join(platforms)}"
        )
        try:
            paths = download_ventoy_release(
                out,
                platforms=platforms,
                keep_archive=keep_archive,
                console=console,
            )
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from e
        for p in paths:
            console.print(f"  → {p}")
        console.print(
            "\n[yellow]Siguiente paso:[/yellow] ejecuta Ventoy2Disk "
            "(Windows .exe o Linux .sh) del directorio extraído para "
            "[bold]actualizar el bootloader[/bold] del USB. "
            "Las ISOs no se tocan."
        )
        if ventoy.is_dir():
            st = check_ventoy(ventoy, online=not offline)
            console.print()
            console.print(format_ventoy_console(st))
        return

    st = check_ventoy(ventoy, online=not offline)
    console.print(format_ventoy_console(st))
    if json_out:
        import json

        json_out.write_text(
            json.dumps(st.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"JSON → {json_out.resolve()}")
    if st.status == "OUTDATED":
        console.print(
            "\n[dim]Descarga el paquete con:[/dim] "
            "[bold]ventoy-iso-check ventoy --fetch[/bold] "
            "[dim](no instala el bootloader; usa Ventoy2Disk después).[/dim]"
        )
        raise typer.Exit(1)
    if st.status in ("ERROR", "NOT_FOUND"):
        raise typer.Exit(2)


@app.command("bootloaders")
def bootloaders_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
    ),
    offline: bool = typer.Option(False, "--offline"),
    json_out: Path | None = typer.Option(None, "--json"),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Inventario de Bootloaders/: Ventoy, Rufus, balenaEtcher vs upstream."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    tools = check_bootloaders(ventoy, online=not offline)
    console.print(format_bootloaders_console(tools))
    if json_out:
        import json

        json_out.write_text(
            json.dumps([t.to_dict() for t in tools], indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        console.print(f"JSON → {json_out.resolve()}")
    if any(t.status == "OUTDATED" for t in tools):
        raise typer.Exit(1)
    if any(t.status == "ERROR" for t in tools):
        raise typer.Exit(2)


@app.command("suggest")
def suggest_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
    ),
    catalog: Path | None = typer.Option(None, "--catalog", "-c"),
    deep: bool = typer.Option(False, "--deep"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Escribir YAML sugerido a un archivo (default: stdout).",
    ),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """Sugerir entradas catalog.yaml para ISOs UNSUPPORTED (sin tocar el disco)."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    suggestions = suggest_unsupported(
        ventoy, catalog_path=catalog, deep=deep
    )
    text = format_suggestions(suggestions)
    if output:
        output.write_text(text, encoding="utf-8")
        console.print(
            f"[green]{len(suggestions)} sugerencia(s) →[/green] {output.resolve()}"
        )
    else:
        # raw YAML to stdout for easy copy-paste
        print(text, end="")
    if not suggestions:
        console.print(
            "[dim]Tip: añade distros a catalog.yaml o copia ISOs nuevas al volumen.[/dim]"
        )


@app.command("download")
def download_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz Ventoy (reescribe directory en sisou.toml al vuelo).",
        exists=False,
        file_okay=False,
        dir_okay=True,
    ),
    sisou_config: Path | None = typer.Option(
        None,
        "--sisou-config",
        help="Ruta a sisou.toml (default: el del proyecto).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mostrar el comando sisou sin ejecutarlo."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Continuar aunque el espacio libre esté por debajo del umbral de abort.",
    ),
    warn_gib: float = typer.Option(
        8.0,
        "--warn-gib",
        help="Advertir si el libre es menor que este valor (GiB).",
    ),
    abort_gib: float = typer.Option(
        2.0,
        "--abort-gib",
        help="Abortar si el libre es menor que este valor (GiB), salvo --force.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """Descargar/actualizar ISOs soportadas mediante SuperISOUpdater (sisou).

    Requiere red y espacio libre. En host: uv + Python 3.12. En Docker: sisou embebido.
    Antes de lanzar sisou comprueba espacio libre en el volumen (Fase 2).
    """
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    cfg = sisou_config or default_sisou_toml()
    console.print(
        f"[bold]Descarga con sisou[/bold]\n"
        f"  config plantilla: {cfg}\n"
        f"  ventoy root:      {ventoy}\n"
        f"  proyecto:         {project_root()}\n"
        f"  dry_run={dry_run}  force={force}"
    )
    if not ventoy.is_dir():
        if dry_run:
            console.print(
                f"[yellow]AVISO:[/yellow] el directorio no existe o no está montado: {ventoy}"
            )
        else:
            console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
            raise typer.Exit(2)
    else:
        _space, verdict, space_msg = check_download_space(
            ventoy,
            warn_gib=warn_gib,
            abort_gib=abort_gib,
            force=force,
        )
        if verdict == SpaceVerdict.ABORT:
            console.print(f"[red]{space_msg}[/red]")
            raise typer.Exit(3)
        if verdict == SpaceVerdict.WARN:
            console.print(f"[yellow]{space_msg}[/yellow]")
        elif verdict == SpaceVerdict.UNKNOWN:
            console.print(f"[yellow]{space_msg}[/yellow]")
        else:
            console.print(f"[green]{space_msg}[/green]")

    code = run_sisou(
        cfg,
        ventoy_root=ventoy if ventoy.is_dir() or dry_run else None,
        log_level=log_level,
        dry_run=dry_run,
    )
    raise typer.Exit(code)


meta_app = typer.Typer(
    name="meta",
    help="Gestionar sidecars .meta.json junto a las ISOs (fecha fiable + checksum).",
    no_args_is_help=True,
)
app.add_typer(meta_app, name="meta")


@meta_app.command("seal")
def meta_seal_cmd(
    root: Path | None = typer.Argument(
        None,
        help="Raíz Ventoy (default: $VENTOY_ROOT | /ventoy | /mnt/e).",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        help="Reescribir también ISOs que ya tienen sidecar.",
    ),
    compute_hash: bool = typer.Option(
        False,
        "--hash",
        help="Calcular SHA-256 (lento en USB grande).",
    ),
    recent_minutes: float | None = typer.Option(
        None,
        "--recent-minutes",
        help="Solo ISOs modificadas en los últimos N minutos.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """Escribir sidecars .meta.json para ISOs sin meta (o todas con --all)."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe el directorio Ventoy:[/red] {ventoy}")
        raise typer.Exit(2)
    written = seal_tree(
        ventoy,
        only_missing=not all_files,
        compute_hash=compute_hash,
        recently_modified_minutes=recent_minutes,
    )
    console.print(
        f"[green]Sidecars escritos:[/green] {len(written)} "
        f"(only_missing={not all_files}, hash={compute_hash})"
    )
    for p in written[:20]:
        console.print(f"  {p}")
    if len(written) > 20:
        console.print(f"  … y {len(written) - 20} más")


@meta_app.command("write")
def meta_write_cmd(
    iso: Path = typer.Argument(..., help="Ruta al archivo .iso/.img", exists=True),
    url: str | None = typer.Option(None, "--url", help="URL de origen"),
    catalog_id: str | None = typer.Option(None, "--catalog-id"),
    hash_file: bool = typer.Option(False, "--hash", help="Calcular SHA-256"),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """Crear/actualizar sidecar para una sola ISO."""
    from datetime import datetime

    from ventoy_iso_check.catalog import load_catalog, match_entry

    _setup_log(log_level)
    entries, _ = load_catalog()
    entry, ver = match_entry(iso.name, entries)
    meta = write_meta_for_iso(
        iso,
        catalog_id=catalog_id or (entry.id if entry else None),
        local_version=ver,
        source_url=url,
        downloaded_at=datetime.now(UTC),
        compute_hash=hash_file,
    )
    console.print(
        f"[green]Escrito[/green] {iso.name}.meta.json  "
        f"downloaded_at={meta.downloaded_at}  sha256={bool(meta.sha256)}"
    )


@meta_app.command("verify")
def meta_verify_cmd(
    root: Path | None = typer.Argument(None),
    only: str | None = typer.Option(None, "--only"),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """Verificar SHA-256 de ISOs que tengan hash en el sidecar."""
    _setup_log(log_level)
    ventoy = (root or _root_arg()).resolve()
    if not ventoy.is_dir():
        console.print(f"[red]No existe:[/red] {ventoy}")
        raise typer.Exit(2)
    only_set = {s.strip() for s in only.split(",")} if only else None
    items = run_check(
        ventoy,
        online=False,
        only=only_set,
        verify_checksum=True,
    )
    with_hash = [i for i in items if i.meta_sha256]
    if not with_hash:
        console.print(
            "[yellow]Ninguna ISO con sha256 en sidecar. "
            "Usa: ventoy-iso-check meta seal --hash[/yellow]"
        )
        raise typer.Exit(0)
    ok_n = sum(1 for i in with_hash if i.checksum_ok is True)
    bad = [i for i in with_hash if i.checksum_ok is False]
    console.print(f"Verificados: {len(with_hash)}  OK={ok_n}  FAIL={len(bad)}")
    for i in bad:
        console.print(f"[red]FAIL[/red] {i.relpath}: {i.note}")
    print_table(with_hash, show_dates=True, stale_days=None)
    raise typer.Exit(1 if bad else 0)


if __name__ == "__main__":
    app()
