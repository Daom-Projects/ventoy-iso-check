# Contexto de dominio — ventoy-iso-check

Documento de fondo para agentes. Complementa `AGENTS.md`.

## Problema que resuelve

El usuario mantiene un **USB/HDD con Ventoy** lleno de ISOs (Linux, herramientas de rescate, Windows).  
Quiere saber:

1. Qué ISOs tiene y de qué versión.
2. Si hay una versión más nueva oficial.
3. Enlaces de descarga (sin bajar a ciegas).
4. Opcionalmente, actualizar vía **sisou** (SuperISOUpdater).
5. Si el archivo en disco es **reciente** (mtime / edad).

## Usuarios y entorno

- Autor: desarrollador en **WSL2 + Windows 11**.
- Volumen típico: **`/mnt/e`** (letra `E:`), FS 9p/drvfs, espacio limitado (~80 GB libres variables).
- Ejecución multiplataforma deseada vía **Docker** (`VENTOY_ROOT=/ventoy`).
- Preferencia de paquete Python: **`uv`**.

## Layout del volumen Ventoy (canónico del autor)

```text
/mnt/e/   (o E:\ o /ventoy en Docker)
  Linux/              # Ubuntu, Mint, Fedora, Kali, CachyOS, Tails, Pop!_OS, Budgie, Zorin, pearOS…
  Herramientas/       # Clonezilla, SystemRescue, Rescuezilla, HBCD, Proxmox, Strelec, Kaspersky…
  Windows/
    11/               # Win11 oficial (sisou)
    10/ 7/ 8.1/ XP/ MiniOS/ Server/   # manual / modificados
  Bootloaders/        # instalador Ventoy (no es ISO de OS; fuera de scope habitual)
  tools/ventoy-iso-check/   # opcional: copia del repo en el USB
```

Carpetas a **no escanear** en profundidad (salvo `--deep`): `MediCat.USB.*`, PortableApps, Programs, recycle, System Volume Information.

## Modelo mental de estados

| Status | Significado |
|--------|-------------|
| `OK` | Versión local ≥ latest conocido |
| `OUTDATED` | Hay release más nueva |
| `UNKNOWN` | En catálogo pero sin latest fiable (o offline / Win11 sin API) |
| `MANUAL` | Terceros o EOL: solo inventario + página |
| `UNSUPPORTED` | ISO detectada sin entrada en `catalog.yaml` |
| `ERROR` | Falló red/resolver |

## Capas de gestión (`managed_by`)

| Valor | Quién actualiza | Ejemplo |
|-------|-----------------|---------|
| `sisou` | SuperISOUpdater + `sisou.toml` | Ubuntu, Fedora, Kali, Clonezilla… |
| `catalog` | Resolver propio en `resolvers.py` | Pop!_OS, Ubuntu Budgie, Zorin (parcial) |
| `manual` | Usuario | MiniOS, Strelec, Win7/XP, Kaspersky |

Añadir una distro nueva:

1. Patrón(es) en `catalog.yaml`.
2. Si hay fuente HTTP estable → función en `resolvers.py` + clave en `RESOLVERS`.
3. Si sisou la soporta → bloque en `sisou.toml`.
4. Probar: `uv run ventoy-iso-check check $VENTOY_ROOT --only <id>`.

## Política de “latest” (importante)

Historial de bugs: resolvers **anclados a la serie local** daban falsos `OK`  
(Ubuntu 24.04.4 vs LTS 26.04; Fedora 43 vs 44).

**Política actual:**

- Reportar la **última release publicada con ISO usable**.
- Si la serie local sigue al día en point-release pero hay major/LTS nueva → `OUTDATED` + `note` explicativa.
- Ubuntu server / LTS: objetivo = **última LTS soportada**.
- Fedora: caminar releases nuevas hasta encontrar ISO real (dirs vacíos tempranos).
- Kali/CachyOS/Tails/Proxmox/Clonezilla/SystemRescue/Rescuezilla: ya eran “latest absoluto”.

## Fechas en disco

- `mtime` (y `birthtime` si existe) en `IsoItem`.
- Columnas **File date** / **Age** en tabla; JSON con ISO-8601.
- No confundir con fecha de release upstream.
- En copias entre discos el mtime puede conservarse → no es 100 % “instante de descarga”.
- Mejora futura (fase del plan): sidecar `.meta.json` con `downloaded_at` real.

## SuperISOUpdater (sisou)

- PyPI: `sisou`; repo: https://github.com/JoshuaVandaele/SuperISOUpdater
- Host: `uv tool run --python 3.12 sisou@latest <toml>` (libtorrent wheels en 3.12).
- Docker: intenta instalar `sisou` en la imagen.
- Matching local por plantilla `name` con `[[VER]]`, `[[ARCH]]`, etc.
- Nombres no canónicos → puede no ver la ISO vieja y descargar otra; el usuario limpia a mano.

## Riesgos

- I/O lento en `/mnt/e` (9p).
- Descargas multi-GB y poco espacio.
- Scraping de HTML frágil (mirrors cambian).
- Packs modificados (MiniOS, Strelec): legalidad/integridad → solo MANUAL.
- No tocar la partición EFI/Ventoy ni el bootloader salvo fase explícita.

## Decisiones de producto ya tomadas

1. Híbrido propio + sisou (no reimplementar todos los mirrors de sisou).
2. CLI Typer + Rich; sin GUI.
3. Portable: Docker + `VENTOY_ROOT`.
4. Catálogo YAML editable por humanos.
5. Idioma de UI: español; código: inglés.

## Inventario típico del autor (orientativo)

Cambia con el tiempo; **no hardcodear versiones en código**. Última revisión de diseño: 2026-07.

- Linux: Ubuntu desktop/server, Budgie, Mint, Fedora WS/SB, Kali, CachyOS, Tails, Pop!_OS, Zorin, pearOS.
- Tools: Clonezilla, SystemRescue, Rescuezilla, HBCD, Proxmox, Strelec, Kaspersky.
- Windows: 11 ES-MX (sisou), 10/7/8.1/XP/Server/MiniOS (manual).

## Documentación del repo (mapa)

| Doc | Rol |
|-----|-----|
| `README.md` | Usuario final |
| `CHANGELOG.md` | Releases |
| `CONTRIBUTING.md` | Contribuciones |
| `AGENTS.md` / `CLAUDE.md` | Agentes |
| `docs/PHASED_PLAN.md` | Roadmap ejecutable (fase actual: **1**) |
| `docs/ARCHITECTURE.md` | Módulos y flujos |

## Referencias

- Ventoy: https://www.ventoy.net/
- SISOU: https://github.com/JoshuaVandaele/SuperISOUpdater
- Plan de fases: [PHASED_PLAN.md](./PHASED_PLAN.md)
