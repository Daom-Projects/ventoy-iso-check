# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado semántico aproximado.

## [0.6.0] — 2026-07-25

### Añadido

- **Fase 3:** cache de latest en `~/.cache/ventoy-iso-check/latest.json` (TTL 12 h).
  - Flags: `--no-cache`, `--refresh`, `--cache-dir`, `--ttl-hours`.
  - Stats en consola: hits/misses/stores.
- Validación en disco real de fases 1 y 2 (`/mnt/e`).

### Cambiado

- Versión 0.5.0 → 0.6.0.
- Plan: Fase 3 done; siguiente Fase 4 (sidecar + checksum).

## [0.5.0] — 2026-07-25

### Añadido

- **Fase 2:** pre-check de espacio libre en `download` (`disk.py`).
  - Muestra libre/total en GiB.
  - **WARN** si libre &lt; `--warn-gib` (default 8).
  - **ABORT** (exit 3) si libre &lt; `--abort-gib` (default 2), salvo `--force`.
- Guía [docs/WINDOWS.md](./docs/WINDOWS.md): probar desde PowerShell (Docker / uv / WSL).

### Cambiado

- Versión 0.4.0 → 0.5.0.
- Plan: Fase 2 completada; siguiente Fase 3 (cache).

## [0.4.0] — 2026-07-25

### Añadido

- **Fase 1:** filtros `--only-outdated`, `--only-stale`, `--only-actionable` (combinables con `--only` y `--stale-days`).
- Catálogo: **elementary OS**, **VirtIO Win**, **Linux Mint MATE/XFCE**.
- Patrones actualizados: Zorin `18.1-Core`, Win11 `es-mx_25H2_…`.
- Resolvers `elementary` y `virtio_win`.

### Cambiado

- Versión 0.3.0 → 0.4.0.
- Plan de fases: Fase 1 marcada como completada.

## [0.3.0] — 2026-07-24

### Añadido

- Columnas **File date** y **Age** (mtime / birthtime del ISO en el disco).
- Flags `--sort path|date|age|status`, `--stale-days N`, `--no-dates`.
- Export de fechas en JSON y `links.md`.
- Documentación para agentes: `AGENTS.md`, `CLAUDE.md`, `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/PHASED_PLAN.md`.
- Instrucciones Copilot: `.github/copilot-instructions.md`.

### Cambiado

- Versión de paquete 0.2.0 → 0.3.0.

## [0.2.0] — 2026-07-24

### Añadido

- Soporte **Pop!_OS** (`catalog` + resolver `iso.pop-os.org`).
- Política **LTS-aware** en Ubuntu (p. ej. 24.04.x → 26.04 como objetivo).
- Fedora y Linux Mint: preferir **última major/release** publicada (no anclar a la major local).
- Portabilidad: `VENTOY_ROOT`, materialización dinámica de `sisou.toml`.
- Docker multi-stage + `docker-compose` + `scripts/run-docker.sh`.

### Corregido

- Falsos `OK` en Ubuntu server 24.04 cuando ya existía LTS más nueva.
- Falsos `OK` en Fedora 43 cuando existía 44.
- MiniOS no clasificado como Windows XP/Server por orden de patrones.

## [0.1.0] — 2026-07-24

### Añadido

- CLI inicial: `scan`, `check`, `links`, `download`.
- `catalog.yaml` + resolvers HTTP para distros habituales.
- Integración SuperISOUpdater (`sisou`) vía `uv` / imagen Docker.
- Layout adaptado a `Linux/`, `Herramientas/`, `Windows/11`.

[0.3.0]: https://github.com/Daom-Projects/ventoy-iso-check/compare/51631e0...0ca3b37
[0.2.0]: https://github.com/Daom-Projects/ventoy-iso-check/commits/main
[0.1.0]: https://github.com/Daom-Projects/ventoy-iso-check/commits/51631e0
