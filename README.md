# ventoy-iso-check

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Inventario y comprobación de ISOs **desactualizadas** en un disco [Ventoy](https://www.ventoy.net/).  
Enfoque **híbrido**:

1. **`ventoy-iso-check`** — escanea el árbol, parsea versiones del nombre de archivo, consulta fuentes oficiales y genera informe + enlaces.
2. **[SuperISOUpdater (sisou)](https://github.com/JoshuaVandaele/SuperISOUpdater)** — descarga y verifica checksums de las distros soportadas (`sisou.toml`).

> Por defecto **no descarga nada**.

Repositorio: [github.com/Daom-Projects/ventoy-iso-check](https://github.com/Daom-Projects/ventoy-iso-check)

### Documentación para agentes y roadmap

| Documento | Contenido |
|-----------|-----------|
| [AGENTS.md](./AGENTS.md) | Instrucciones para agentes de código |
| [docs/CONTEXT.md](./docs/CONTEXT.md) | Contexto de dominio (Ventoy, WSL, políticas) |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Arquitectura de módulos |
| [docs/PHASED_PLAN.md](./docs/PHASED_PLAN.md) | **Plan de mejoras por fases** (ejecutable) |

---

## ¿Se puede ejecutar desde el mismo disco en Linux, macOS y Windows?

**Sí, con matices.** La forma más portable y recomendada es **Docker**: el mismo comando monta la partición Ventoy en `/ventoy` y el contenedor es idéntico en los tres SO.

| Método | Linux | macOS | Windows | Notas |
|--------|:-----:|:-----:|:-------:|-------|
| **Docker** (recomendado) | ✅ | ✅ | ✅ (Docker Desktop) | Monta la partición en `/ventoy` |
| **uv / Python nativo** | ✅ | ✅ | ✅ (WSL2 o Python nativo) | Ideal en WSL o Linux |
| **Código en el USB** | ✅ | ✅ | ✅ | Copia el repo a `tools/ventoy-iso-check/` y monta/ejecuta |
| **sisou download** | ✅ | ⚠️ | ✅ | En host requiere Python 3.12 + uv; en Docker va embebido si el build lo instaló |

### Convención de rutas

| Contexto | Raíz Ventoy |
|----------|-------------|
| Variable de entorno | `$VENTOY_ROOT` o `$VENTOY_HOST` (compose) |
| Dentro de Docker | `/ventoy` |
| WSL (letra E:) | `/mnt/e` |
| Linux típico | `/media/$USER/Ventoy` o `/run/media/$USER/Ventoy` |
| macOS | `/Volumes/Ventoy` (nombre del volumen) |
| Windows nativo | `E:\` (Docker Desktop) o WSL `/mnt/e` |

La CLI resuelve la raíz en este orden: **`$VENTOY_ROOT` → `/ventoy` (si existe) → `/mnt/e` (si existe) → cwd**.

Puedes llevar el código **en el propio USB**:

```text
E:\  (o /ventoy)
├── Linux/
├── Herramientas/
├── Windows/
└── tools/
    └── ventoy-iso-check/    ← este repo (git clone / copia)
```

Eso no hace el USB “arrancable con la tool”: Ventoy sigue sirviendo ISOs al boot. La tool se ejecuta **desde un SO anfitrión** (o Docker) con el volumen montado.

---

## Inicio rápido con Docker

### Requisitos

- [Docker](https://docs.docker.com/get-docker/) (o Docker Desktop en Windows/macOS)
- Partición Ventoy montada y visible en el host

### Build

```bash
git clone https://github.com/Daom-Projects/ventoy-iso-check.git
cd ventoy-iso-check
docker build -t ventoy-iso-check:local .
```

### Ejecutar

```bash
# Linux / WSL — ajusta la ruta del host
docker run --rm -v /mnt/e:/ventoy ventoy-iso-check:local scan
docker run --rm -v /mnt/e:/ventoy ventoy-iso-check:local check --urls
docker run --rm -v /mnt/e:/ventoy ventoy-iso-check:local links -o /ventoy/links.md

# macOS
docker run --rm -v /Volumes/Ventoy:/ventoy ventoy-iso-check:local check

# Windows (PowerShell / Docker Desktop) — letra de unidad del Ventoy
docker run --rm -v E:\:/ventoy ventoy-iso-check:local check
```

### docker compose

```bash
# Define la ruta del host
export VENTOY_HOST=/mnt/e          # WSL/Linux
# export VENTOY_HOST=/Volumes/Ventoy
# set VENTOY_HOST=E:\              # Windows

docker compose run --rm vic scan
docker compose run --rm vic check --urls
docker compose run --rm vic links -o /ventoy/links.md
docker compose run --rm vic download --dry-run
```

Script helper:

```bash
VENTOY_HOST=/mnt/e ./scripts/run-docker.sh check --only ubuntu,kali
```

---

## Inicio rápido con uv (sin Docker)

### Requisitos

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/Daom-Projects/ventoy-iso-check.git
cd ventoy-iso-check
uv sync

export VENTOY_ROOT=/mnt/e   # o la ruta de tu SO
uv run ventoy-iso-check scan
uv run ventoy-iso-check check --urls
uv run ventoy-iso-check links -o links.md
uv run ventoy-iso-check download --dry-run
```

También puedes pasar la ruta como argumento:

```bash
uv run ventoy-iso-check check /mnt/e
uv run ventoy-iso-check check /Volumes/Ventoy
```

### Descarga real (`download` / sisou)

```bash
# Dry-run
uv run ventoy-iso-check download /mnt/e --dry-run

# Real (reescribe directory en sisou.toml al vuelo con la raíz que indiques)
uv run ventoy-iso-check download /mnt/e
```

En host sin imagen Docker, `download` usa:

```bash
uv tool run --python 3.12 sisou@latest <config-temporal>
```

Python **3.12** es necesario para wheels de `libtorrent` (dependencia de sisou).

---

## Comandos CLI

| Comando | Red | Efecto |
|---------|-----|--------|
| `scan [ROOT]` | No | Inventario local |
| `check [ROOT]` | Sí | Compara con últimas versiones |
| `links [ROOT] -o FILE` | Sí | Markdown con URLs |
| `download [ROOT]` | Sí | Actualiza vía sisou |
| `--only a,b` | — | Filtra por id/nombre |
| `--urls` | — | Columna URL en tabla |
| `--deep` | — | Incluye árboles tipo MediCat |
| `--offline` | — | check sin red |
| `--dry-run` | — | download sin ejecutar |
| `--sort path\|date\|age\|status` | — | Orden de la tabla |
| `--stale-days N` | — | Resalta archivos con mtime ≥ N días (default 180; `0` = off) |
| `--no-dates` | — | Oculta columnas File date / Age |

### Fecha del archivo (copia / descarga)

Cada fila muestra:

- **File date** — `mtime` del ISO en el disco (en la práctica: cuándo se copió o descargó al volumen). Si el FS expone `birthtime`, se usa como preferencia.
- **Age** — antigüedad relativa (`3d`, `2.1mo`, `1.5y`). Colores: verde &lt; 30d, amarillo &lt; 180d, rojo ≥ 180d (o el umbral de `--stale-days`).

```bash
# Más antiguas primero
uv run ventoy-iso-check scan /mnt/e --sort age

# Solo “viejas” visualmente (mtime ≥ 90 días)
uv run ventoy-iso-check scan /mnt/e --stale-days 90 --sort age
```

> **Nota:** en copias entre discos, el SO a veces conserva el mtime original del archivo; no siempre es el instante exacto de la última descarga.

---

## Layout de ISOs esperado

```text
/ventoy/   (o /mnt/e, E:\, …)
  Linux/           # Ubuntu, Mint, Fedora, Kali, CachyOS, Tails, …
  Herramientas/    # Clonezilla, SystemRescue, Rescuezilla, HBCD, Proxmox, …
  Windows/11/      # Win11_* (sisou, Spanish Mexico)
  tools/           # opcional: copia de este proyecto
```

Configura ediciones/idiomas en `sisou.toml`. El campo `directory` es plantilla: **`download` lo sustituye** por la raíz real en un TOML temporal.

---

## Qué cubre cada capa

| Origen | Acción |
|--------|--------|
| Ubuntu, Mint, Fedora, Kali, CachyOS, Tails, Proxmox, Clonezilla, SystemRescue, Rescuezilla, Hiren's, Win11 | `check` + `download` (sisou) |
| Ubuntu Budgie, Zorin | `check` / `links` |
| MiniOS, Strelec, MediCat, Kaspersky, Win legacy/Server | `MANUAL` (inventario + nota) |

---

## Archivos del proyecto

| Archivo | Rol |
|---------|-----|
| `src/ventoy_iso_check/` | CLI y lógica |
| `catalog.yaml` | Patrones, resolvers, páginas oficiales |
| `sisou.toml` | Config SuperISOUpdater (plantilla) |
| `Dockerfile` / `docker-compose.yml` | Imagen portable |
| `scripts/run-docker.sh` | Atajo Docker |

---

## Notas por plataforma

### WSL2 (Windows 11)

- Montaje típico: `/mnt/e` (lento vía 9p).
- Para ISOs grandes: descarga en el FS de Linux y mueve, o usa Docker Desktop montando `E:\`.
- `uv` + Python 3.12 en WSL funciona bien para `scan`/`check`/`links`.

### Linux

- Monta el USB/exFAT/NTFS y exporta `VENTOY_ROOT`.
- Docker o uv indistintamente.

### macOS

- El volumen suele aparecer en `/Volumes/<Nombre>`.
- Docker Desktop requiere permitir el acceso al volumen en Settings → Resources → File sharing.

### Windows (sin WSL)

- Usa **Docker Desktop** y `-v E:\:/ventoy`.
- Alternativa: Python nativo + `uv` (más fricción con rutas y sisou).

### Espacio y seguridad

- Revisa GB libres antes de `download`.
- MediCat y árboles enormes se omiten salvo `--deep`.
- Ventoy (bootloader) se actualiza **aparte**; no lo gestiona esta tool.
- Packs de terceros (MiniOS, Strelec) no se auto-actualizan.

---

## Limitaciones

- Los resolvers hacen scraping/listados de mirrors; pueden fallar si cambia el HTML.
- SISOU identifica ISOs por el patrón `name` (`[[VER]]`, …). Nombres no canónicos pueden requerir renombre o limpieza manual.
- Rescuezilla en SISOU: ediciones `noble` / `resolute` (no `plucky`).
- Windows 7/8/10/XP/Server y builds modificados: sin auto-update fiable.
- La imagen Docker intenta instalar `sisou`; si falla el build de dependencias nativas, `scan`/`check`/`links` siguen disponibles y `download` puede hacerse en el host con uv.

---

## Desarrollo

```bash
uv sync
uv run ventoy-iso-check --help
docker build -t ventoy-iso-check:local .
```

---

## Licencia

MIT © Daom-Projects.  
SuperISOUpdater (sisou) es un proyecto de terceros bajo **GPL-2.0-or-later**.
