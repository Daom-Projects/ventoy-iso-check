# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado semántico aproximado.

## [0.10.0] — 2026-07-25

### Añadido

- **Fase 7:** suite `pytest` (version_cmp, catalog, filters, policy, meta, suggest, ubuntu mock, checker).
- Resolución HTTP en **paralelo** (`ThreadPoolExecutor`, `--workers`, default 8).
- Dev deps: `pytest`, `respx`.
- `make test`.

### Cambiado

- Versión 0.9.0 → 0.10.0.
- Plan: Fase 7 done; siguiente Fase 8 (export + Ventoy bootloader).

## [0.9.0] — 2026-07-25

### Añadido

- **Fase 6:** comando `suggest` → YAML para ISOs `UNSUPPORTED`.
- Catálogo + resolvers: **Debian netinst**, **Arch Linux**, **GParted Live**, **Memtest86+**.
- pearOS con resolver best-effort (GitHub / página).
- `docs/ARCHITECTURE.md` ampliado (checklist para añadir distros).

### Cambiado

- Versión 0.8.0 → 0.9.0.
- Plan: Fase 6 done; siguiente Fase 7 (tests + HTTP paralelo).

## [0.8.0] — 2026-07-25

### Añadido

- **Fase 5:** política de actualización `--policy latest|latest-lts|same-series`.
  - Default: `latest-lts` (Ubuntu server/LTS; Fedora/Mint ≈ latest).
  - `same-series`: solo point-releases de la serie local (taller multi-LTS).
  - `--hint-newer-lts`: anota LTS/release más nueva sin marcar OUTDATED.
- Aplica a Ubuntu, Budgie, Mint, Fedora, Pop!_OS; cache key incluye policy.

### Cambiado

- Versión 0.7.0 → 0.8.0.
- Plan: Fase 5 done; siguiente Fase 6 (suggest + más distros).

## [0.7.0] — 2026-07-25

### Añadido

- **Fase 4:** sidecars `foo.iso.meta.json` con `downloaded_at`, `source_url`, `sha256`.
  - Comandos: `meta seal`, `meta write`, `meta verify`.
  - Age/File date prefieren `downloaded_at` del sidecar (columna Meta ✓).
  - `--verify-checksum` en scan/check; mismatch → ERROR sin borrar la ISO.
  - Post-`download` sisou: sella ISOs modificadas en los últimos 120 min.
- Módulo `meta.py`.

### Cambiado

- Versión 0.6.0 → 0.7.0.
- Plan: Fase 4 done; siguiente Fase 5 (multi-LTS).

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
