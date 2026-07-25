# ventoy-iso-check

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/packaging-uv-de5fe9.svg)](https://docs.astral.sh/uv/)
[![Version](https://img.shields.io/badge/version-0.9.0-green.svg)](./CHANGELOG.md)

Inventario y comprobación de ISOs **desactualizadas** en un disco [Ventoy](https://www.ventoy.net/).

**Enfoque híbrido:**

1. **`ventoy-iso-check`** — escanea el árbol, parsea versiones, consulta fuentes oficiales, muestra **fecha/edad del archivo en disco** y genera informe + enlaces.
2. **[SuperISOUpdater (sisou)](https://github.com/JoshuaVandaele/SuperISOUpdater)** — descarga y verifica checksums de distros soportadas (`sisou.toml`).

> Por defecto **no descarga nada**.

| | |
|--|--|
| **Repositorio** | [github.com/Daom-Projects/ventoy-iso-check](https://github.com/Daom-Projects/ventoy-iso-check) |
| **Organización** | [Daom-Projects](https://github.com/Daom-Projects) |
| **Changelog** | [CHANGELOG.md](./CHANGELOG.md) |
| **Contribuir** | [CONTRIBUTING.md](./CONTRIBUTING.md) |

### Documentación para agentes y roadmap

| Documento | Contenido |
|-----------|-----------|
| [AGENTS.md](./AGENTS.md) | Instrucciones para agentes de código |
| [CLAUDE.md](./CLAUDE.md) | Puntero Claude Code |
| [docs/CONTEXT.md](./docs/CONTEXT.md) | Dominio Ventoy / WSL / políticas |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Arquitectura de módulos |
| [docs/PHASED_PLAN.md](./docs/PHASED_PLAN.md) | **Plan de mejoras por fases** (ejecutable) |
| [docs/README.md](./docs/README.md) | Índice de docs internas |

---

## Características (v0.9.0)

- Inventario de `*.iso` / `*.img` con etiqueta, versión local y tamaño.
- Comparación con **última release publicada** (Ubuntu LTS-aware, Fedora major, etc.).
- **File date** + **Age** (mtime o **sidecar** `downloaded_at`).
- Sidecars **`.meta.json`**: fecha fiable, URL, SHA-256 opcional.
- **Política multi-LTS**: `--policy latest|latest-lts|same-series`.
- **`suggest`**: genera YAML para ISOs aún no catalogadas.
- Filtros: **`--only-outdated`**, **`--only-stale`**, **`--only-actionable`**.
- **Pre-check de espacio** en `download` (WARN / ABORT + `--force`).
- **Cache de latest** (TTL 12 h, `~/.cache/ventoy-iso-check/`).
- Generación de **enlaces** (Markdown) y export **JSON**.
- Descarga opcional vía **sisou** (Python 3.12 / Docker).
- Portable: **Docker**, **uv**, variables `$VENTOY_ROOT` / `$VENTOY_HOST`.
- Catálogo editable (`catalog.yaml`) + plantilla `sisou.toml`.
- Guía Windows: [docs/WINDOWS.md](./docs/WINDOWS.md).

### Estados

| Status | Significado |
|--------|-------------|
| `OK` | Local al día respecto al latest conocido |
| `OUTDATED` | Hay versión más nueva |
| `UNKNOWN` | En catálogo, sin latest fiable / offline |
| `MANUAL` | Terceros o EOL (solo inventario) |
| `UNSUPPORTED` | Detectada, sin entrada en catálogo |
| `ERROR` | Fallo de red o del resolver |

---

## ¿Se puede ejecutar desde el mismo disco en Linux, macOS y Windows?

**Sí, con matices.** La forma más portable es **Docker**: monta la partición Ventoy en `/ventoy`.

| Método | Linux | macOS | Windows | Notas |
|--------|:-----:|:-----:|:-------:|-------|
| **Docker** | ✅ | ✅ | ✅ (Docker Desktop) | Monta en `/ventoy` |
| **uv / Python** | ✅ | ✅ | ✅ (WSL2 o nativo) | Ideal en WSL |
| **Código en el USB** | ✅ | ✅ | ✅ | p. ej. `tools/ventoy-iso-check/` |
| **sisou download** | ✅ | ⚠️ | ✅ | Host: Python 3.12 + uv |

### Convención de rutas

| Contexto | Raíz Ventoy |
|----------|-------------|
| Variable | `$VENTOY_ROOT` o `$VENTOY_HOST` (compose) |
| Docker | `/ventoy` |
| WSL (`E:`) | `/mnt/e` |
| Linux | `/media/$USER/Ventoy`, `/run/media/$USER/Ventoy` |
| macOS | `/Volumes/Ventoy` |
| Windows | `E:\` (Docker Desktop) |

Orden de resolución en CLI: **`$VENTOY_ROOT` → `/ventoy` → `/mnt/e` → cwd**.

```text
E:\  (o /ventoy)
├── Linux/
├── Herramientas/
├── Windows/
└── tools/
    └── ventoy-iso-check/    ← opcional: copia de este repo
```

Ventoy sigue sirviendo ISOs al boot; la tool se ejecuta desde el **SO anfitrión** o un contenedor.

---

## Inicio rápido con Docker

```bash
git clone https://github.com/Daom-Projects/ventoy-iso-check.git
cd ventoy-iso-check
docker build -t ventoy-iso-check:local .

# WSL / Linux
docker run --rm -v /mnt/e:/ventoy ventoy-iso-check:local scan
docker run --rm -v /mnt/e:/ventoy ventoy-iso-check:local check --urls

# macOS
docker run --rm -v /Volumes/Ventoy:/ventoy ventoy-iso-check:local check

# Windows (Docker Desktop)
docker run --rm -v E:\:/ventoy ventoy-iso-check:local check
```

### docker compose

```bash
export VENTOY_HOST=/mnt/e   # o /Volumes/Ventoy  o  E:\
docker compose run --rm vic scan
docker compose run --rm vic check --urls --sort age
docker compose run --rm vic download --dry-run
```

```bash
VENTOY_HOST=/mnt/e ./scripts/run-docker.sh check --only ubuntu,kali
```

---

## Inicio rápido con uv

Requisitos: **Python 3.12+**, [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Daom-Projects/ventoy-iso-check.git
cd ventoy-iso-check
uv sync

export VENTOY_ROOT=/mnt/e
uv run ventoy-iso-check scan
uv run ventoy-iso-check check --urls --sort age
uv run ventoy-iso-check links -o links.md
uv run ventoy-iso-check download --dry-run
```

### Descarga real (`download` / sisou)

```bash
# Muestra espacio libre y el comando sisou (sin bajar)
uv run ventoy-iso-check download /mnt/e --dry-run

# Real
uv run ventoy-iso-check download /mnt/e

# Umbrales (GiB): WARN por defecto 8, ABORT por defecto 2
uv run ventoy-iso-check download /mnt/e --warn-gib 10 --abort-gib 3
uv run ventoy-iso-check download /mnt/e --force   # ignora ABORT de espacio
```

| Flag download | Efecto |
|---------------|--------|
| `--dry-run` | No ejecuta sisou |
| `--force` | Continúa aunque libre &lt; `--abort-gib` |
| `--warn-gib N` | Advertencia si libre &lt; N GiB (default 8) |
| `--abort-gib N` | Exit 3 si libre &lt; N GiB (default 2) |

En host, internamente:

```bash
uv tool run --python 3.12 sisou@latest <config-temporal>
```

Python **3.12** es necesario para wheels de `libtorrent` (dependencia de sisou).

### Probar desde Windows (PowerShell)

Ver guía completa: **[docs/WINDOWS.md](./docs/WINDOWS.md)**.

```powershell
# Docker Desktop (recomendado)
cd path\to\ventoy-iso-check
git pull
docker build -t ventoy-iso-check:local .
docker run --rm -v E:\:/ventoy ventoy-iso-check:local scan
docker run --rm -v E:\:/ventoy ventoy-iso-check:local check --only-outdated --urls
docker run --rm -v E:\:/ventoy ventoy-iso-check:local download --dry-run
```

---

## Comandos CLI

| Comando | Red | Efecto |
|---------|-----|--------|
| `scan [ROOT]` | No | Inventario local + fechas |
| `check [ROOT]` | Sí | Compara con latest (sin descargar) |
| `links [ROOT] -o FILE` | Sí | Markdown con URLs |
| `download [ROOT]` | Sí | Actualiza vía sisou (+ seal meta recientes) |
| `meta seal [ROOT]` | No | Escribe `.meta.json` faltantes |
| `meta write ISO` | No | Sidecar de una ISO (`--url`, `--hash`) |
| `meta verify [ROOT]` | No | Verifica SHA-256 de sidecars con hash |
| `suggest [ROOT]` | No | YAML sugerido para ISOs UNSUPPORTED |

| Flag | Efecto |
|------|--------|
| `--only a,b` | Filtro por id / etiqueta / nombre |
| `--urls` | Columna URL/página |
| `--deep` | Incluye árboles tipo MediCat |
| `--offline` | `check` sin red |
| `--dry-run` | `download` sin ejecutar |
| `--json PATH` | Export JSON |
| `--sort path\|date\|age\|status` | Orden de la tabla |
| `--stale-days N` | Umbral de antigüedad (default 180; `0` = off) |
| `--only-outdated` | Solo status OUTDATED |
| `--only-stale` | Solo age ≥ `--stale-days` |
| `--only-actionable` | OUTDATED + ERROR + stale |
| `--no-cache` | No leer/escribir cache de latest |
| `--refresh` | Forzar reconsulta de red (sí guarda cache) |
| `--cache-dir DIR` | Ubicación del cache (default `~/.cache/ventoy-iso-check`) |
| `--ttl-hours N` | TTL del cache (default 12) |
| `--verify-checksum` | Verifica SHA-256 de sidecars (lento) |
| `--policy POLICY` | `latest` \| `latest-lts` (default) \| `same-series` |
| `--hint-newer-lts` | Con same-series, anota LTS/release más nueva |
| `--no-dates` | Oculta File date / Age |
| `-V` / `--version` | Versión del paquete |

```bash
# Taller: conservar 24.04 y 26.04 sin marcar 24.04 como OUTDATED
uv run ventoy-iso-check check /mnt/e --only ubuntu --policy same-series --hint-newer-lts

# Objetivo = última LTS (default para server/LTS)
uv run ventoy-iso-check check /mnt/e --only ubuntu --policy latest-lts
```

### Sidecars (`.iso.meta.json`)

```bash
# Generar meta para ISOs sin sidecar (usa mtime como downloaded_at)
uv run ventoy-iso-check meta seal /mnt/e

# Una ISO + hash SHA-256
uv run ventoy-iso-check meta write /mnt/e/Herramientas/virtio-win-0.1.285.iso \
  --url "https://…" --hash

# Verificar integridad (solo las que tienen sha256 en meta)
uv run ventoy-iso-check meta verify /mnt/e
uv run ventoy-iso-check check /mnt/e --verify-checksum --only virtio
```

> El `*` en File date indica que la fecha viene del sidecar, no solo del FS.

```bash
# Solo lo que hay que actualizar (versión)
uv run ventoy-iso-check check /mnt/e --only-outdated --urls

# Solo archivos viejos en el disco (≥ 90 días)
uv run ventoy-iso-check scan /mnt/e --only-stale --stale-days 90 --sort age

# Todo lo accionable
uv run ventoy-iso-check check /mnt/e --only-actionable --sort status
```

### Makefile

```bash
make scan VENTOY_HOST=/mnt/e
make check VENTOY_HOST=/mnt/e
make docker-build
make docker-check VENTOY_HOST=/mnt/e
```

### Fecha del archivo (copia / descarga)

| Columna | Significado |
|---------|-------------|
| **File date** | `mtime` (o birthtime) del ISO en el disco |
| **Age** | Antigüedad: `3d`, `2.1mo`, `1.5y` |

Colores: verde &lt; 30d · amarillo &lt; 180d · rojo ≥ umbral (`--stale-days`).

```bash
uv run ventoy-iso-check scan /mnt/e --sort age
uv run ventoy-iso-check scan /mnt/e --stale-days 90 --sort age
```

> En copias entre discos el SO puede conservar el mtime original. No es la fecha de *release* de la distro. Mejora planificada: sidecar `.meta.json` (fase 4 del plan).

---

## Layout de ISOs esperado

```text
/ventoy/   (o /mnt/e, E:\, …)
  Linux/           # Ubuntu, Mint, Fedora, Kali, CachyOS, Tails, Pop!_OS, …
  Herramientas/    # Clonezilla, SystemRescue, Rescuezilla, HBCD, Proxmox, …
  Windows/11/      # Win11_* (sisou; Spanish Mexico en plantilla)
  tools/           # opcional: copia de este proyecto
```

`sisou.toml`: ediciones/idiomas; `directory` es plantilla y **`download` lo reescribe** a la raíz real.

---

## Cobertura del catálogo

### Check + download (sisou / bien soportados)

Ubuntu (desktop, live-server), Linux Mint Cinnamon, Fedora (Workstation, Silverblue), Kali, CachyOS, Tails, Proxmox VE, Clonezilla, SystemRescue, Rescuezilla, Hiren's BootCD PE, Windows 11 (vía sisou).

### Check / links (catálogo propio)

Pop!_OS, Ubuntu Budgie, Linux Mint MATE/XFCE, elementary OS, VirtIO Win,  
Debian netinst, Arch Linux, GParted Live, Memtest86+, pearOS,  
Zorin (página; CDN con token).

```bash
# Si copias una ISO desconocida al USB:
uv run ventoy-iso-check suggest /mnt/e
# pega el YAML en catalog.yaml, ajusta page/resolver, y re-ejecuta check
```

### Solo inventario (manual)

MiniOS, Strelec, MediCat, Kaspersky Rescue, Windows 7/8.1/10/XP/Server, pearOS (página).

Política de “latest”: se reporta la **última release publicada con ISO usable** (no se ancla a la major local). Ubuntu server/LTS apunta a la **última LTS** soportada. Ver [docs/CONTEXT.md](./docs/CONTEXT.md).

---

## Archivos del proyecto

| Ruta | Rol |
|------|-----|
| `src/ventoy_iso_check/` | CLI y lógica |
| `catalog.yaml` | Patrones, resolvers, páginas |
| `sisou.toml` | Plantilla SuperISOUpdater |
| `Dockerfile`, `docker-compose.yml` | Imagen portable |
| `scripts/run-docker.sh` | Atajo Docker |
| `docs/` | Contexto, arquitectura, plan por fases |
| `AGENTS.md` | Instrucciones para agentes |
| `CHANGELOG.md` | Historial de versiones |

---

## Notas por plataforma

### WSL2 (Windows 11)

- Montaje típico: `/mnt/e` (lento vía 9p).
- ISOs grandes: descargar en FS Linux y mover, o Docker Desktop con `E:\`.
- `uv` + Python 3.12 recomendado para `scan`/`check`/`links`.

### Linux / macOS / Windows

- Exporta `VENTOY_ROOT` o usa Docker.
- macOS: File sharing de Docker Desktop al volumen.
- Windows sin WSL: Docker Desktop `-v E:\:/ventoy`.

### Espacio y seguridad

- Revisa GB libres antes de `download`.
- MediCat y árboles enormes se omiten salvo `--deep`.
- Bootloader Ventoy se actualiza **aparte**.
- Packs de terceros (MiniOS, Strelec) no se auto-actualizan.

---

## Limitaciones

- Resolvers por scraping/listados de mirrors (HTML puede cambiar).
- SISOU identifica ISOs por plantilla `name` (`[[VER]]`, …); nombres no canónicos pueden requerir renombre.
- Rescuezilla en SISOU: ediciones `noble` / `resolute` (no `plucky`).
- Windows legacy / builds modificados: sin auto-update fiable.
- Si `sisou` no entra en la imagen Docker, `scan`/`check`/`links` siguen OK; `download` en host con uv.

---

## Roadmap

El trabajo futuro está organizado por **fases** en [docs/PHASED_PLAN.md](./docs/PHASED_PLAN.md).

| Fase | Tema | Estado |
|------|------|--------|
| 0 | Baseline + docs agentes | done |
| 1 | `--only-outdated` / `--only-stale` | **done** (v0.4.0) |
| 2 | Espacio libre pre-download | **done** (v0.5.0) |
| 3 | Cache de latest (TTL) | **done** (v0.6.0) |
| 4 | Sidecar metadata + checksum | **done** (v0.7.0) |
| 5 | Multi-LTS / same-series | **done** (v0.8.0) |
| 6 | suggest + más distros | **done** (v0.9.0) |
| 7–9 | tests, export, CI | pending |

Prompt para un agente:

```text
Lee AGENTS.md y docs/PHASED_PLAN.md. Ejecuta la siguiente fase pending.
No descargues ISOs reales. Verifica con uv. Commit, push y actualiza el plan.
```

---

## Desarrollo

```bash
uv sync
uv run ventoy-iso-check --help
uv run ventoy-iso-check -V
docker build -t ventoy-iso-check:local .
```

Ver también [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Licencia

MIT © Daom-Projects.  
SuperISOUpdater (sisou) es un proyecto de terceros bajo **GPL-2.0-or-later**.
