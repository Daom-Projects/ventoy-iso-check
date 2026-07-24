---
title: Plan de mejoras por fases
project: ventoy-iso-check
status: active
last_updated: 2026-07-24
current_phase: 1
version_baseline: "0.3.0"
---

# Plan de mejoras por fases

**Fuente de verdad del roadmap.** Los agentes deben ejecutar **una fase a la vez**, en orden, salvo que el usuario indique otra.

Al completar una fase:

1. Actualizar la tabla de estado abajo (`pending` → `done`).
2. Anotar `completed_at`, `commit` y notas.
3. Bump de versión en `pyproject.toml` / `__init__.py` si la fase es user-facing.
4. Commit + push (o PR).

## Estado global

| Fase | Nombre | Estado | Prioridad |
|------|--------|--------|-----------|
| 0 | Baseline documentado + agentes | **done** | — |
| 1 | Filtros UX (`--only-outdated`, `--only-stale`) | pending | Alta |
| 2 | Pre-check de espacio libre en `download` | pending | Alta |
| 3 | Cache de latest (TTL) | pending | Alta |
| 4 | Sidecar metadata + checksum opcional | pending | Alta |
| 5 | Política multi-LTS / pin de serie | pending | Media |
| 6 | Catálogo: auto-sugerir UNSUPPORTED + más distros | pending | Media |
| 7 | Calidad: tests de resolvers + async HTTP | pending | Media |
| 8 | Export CSV/HTML + check Ventoy bootloader | pending | Baja |
| 9 | CI GitHub Actions (lint/test/docker build) | pending | Baja |

---

## Fase 0 — Baseline (hecho)

**Objetivo:** herramienta usable + docs de agente + portabilidad Docker.

**Entregado (≤ 0.3.0):**

- CLI scan/check/links/download
- catalog.yaml + resolvers (Ubuntu LTS-aware, Fedora latest major, Pop!_OS, …)
- sisou bridge + Docker
- File date / Age (`mtime`)
- AGENTS.md, docs/*

**Verificación:** `uv run ventoy-iso-check scan $VENTOY_ROOT --sort age`

---

## Fase 1 — Filtros UX

**Estado:** `pending`  
**Estimación:** S / 1 sesión  
**Depende de:** 0

### Objetivo

Que el usuario vea solo lo accionable sin scroll de MiniOS/XP.

### Trabajo

- [ ] Flag `--only-outdated` en `check`/`links` (status == OUTDATED).
- [ ] Flag `--only-stale` (age_days ≥ `--stale-days`).
- [ ] Combinables con `--only id1,id2`.
- [ ] Opcional: `--only-actionable` = OUTDATED | ERROR | (stale si se pide).
- [ ] Documentar en README.

### Criterios de aceptación

```bash
uv run ventoy-iso-check check /mnt/e --only-outdated
# solo filas OUTDATED (o mensaje "ninguna")
uv run ventoy-iso-check scan /mnt/e --only-stale --stale-days 90 --sort age
```

### Archivos probables

`cli.py`, `checker.py` o `reporters.py`, `README.md`

### Notas de implementación

Filtrar **después** de `run_check` para no duplicar lógica. Mantener JSON completo si se pide con un flag `--all-json` solo si hace falta; por defecto el filtro aplica también al JSON.

---

## Fase 2 — Espacio libre antes de download

**Estado:** `pending`  
**Estimación:** S  
**Depende de:** 0

### Objetivo

Evitar descargas a medias cuando el USB no tiene espacio.

### Trabajo

- [ ] Función `disk_usage(ventoy_root)` (shutil.disk_usage).
- [ ] En `download` (antes de sisou): mostrar free/total.
- [ ] Si free < umbral (default 8 GiB) → warning; si free < 2 GiB → abort salvo `--force`.
- [ ] Opcional: estimar tamaño solo de updaters enabled (fase posterior si es complejo).

### Criterios de aceptación

```bash
uv run ventoy-iso-check download /mnt/e --dry-run
# imprime espacio libre
# con free simulado bajo: exit != 0 sin --force
```

### Archivos probables

`sisou_bridge.py` o nuevo `disk.py`, `cli.py`

---

## Fase 3 — Cache de latest

**Estado:** `pending`  
**Estimación:** M  
**Depende de:** 0

### Objetivo

`check` rápido en WSL sin re-scrape cada vez.

### Trabajo

- [ ] Cache en `~/.cache/ventoy-iso-check/latest.json` (o `$XDG_CACHE_HOME`).
- [ ] Clave: `resolver + edition + arch` (o catalog id).
- [ ] TTL default 12 h; flags `--no-cache`, `--refresh`.
- [ ] Guardar `ResolveResult` serializable + `fetched_at`.
- [ ] README: mencionar ubicación y flags.

### Criterios de aceptación

```bash
time uv run ventoy-iso-check check /mnt/e --only ubuntu,fedora
time uv run ventoy-iso-check check /mnt/e --only ubuntu,fedora   # 2ª vez mucho más rápida
uv run ventoy-iso-check check /mnt/e --refresh --only ubuntu
```

### Archivos probables

`resolvers.py` o `cache.py`, `checker.py`, `cli.py`

### No hacer

Cachear en el USB por defecto (lento/sucio); opcional flag `--cache-dir` sí.

---

## Fase 4 — Sidecar metadata + checksum

**Estado:** `pending`  
**Estimación:** L  
**Depende de:** 1 (útil), 2 (recomendado)

### Objetivo

Fecha de descarga **fiable** e integridad opcional.

### Diseño del sidecar

Junto a `foo.iso` → `foo.iso.meta.json` (o `foo.meta.json`):

```json
{
  "schema": 1,
  "filename": "foo.iso",
  "downloaded_at": "2026-07-24T18:00:00+00:00",
  "source_url": "https://...",
  "sha256": "optional...",
  "tool": "ventoy-iso-check",
  "tool_version": "0.x.y",
  "catalog_id": "ubuntu-desktop"
}
```

### Trabajo

- [ ] Modelo `IsoMeta` + load/save.
- [ ] inventory: leer sidecar si existe; preferir `downloaded_at` sobre mtime para Age cuando esté.
- [ ] Columna o indicador `meta` en tabla (✓ si hay sidecar).
- [ ] Tras download exitoso (sisou o catalog download): escribir sidecar.
- [ ] Comando o flag `--verify-checksum` (si hay sha256 en meta o URL de CHECKSUMS).
- [ ] `.gitignore` no aplica a sidecars en USB (viven en el volumen, no en git).

### Criterios de aceptación

- Scan muestra age basado en meta cuando existe.
- Tras un download controlado (o escritura manual de meta de prueba), la fecha coincide.
- Checksum mismatch → ERROR o nota clara sin borrar la ISO.

### Archivos probables

`models.py`, `inventory.py`, `meta.py` (nuevo), `sisou_bridge.py`, `reporters.py`, `cli.py`

---

## Fase 5 — Política multi-LTS / pin de serie

**Estado:** `pending`  
**Estimación:** M  
**Depende de:** 0

### Objetivo

En un USB de taller es válido tener **24.04 y 26.04** a la vez.  
No todo el mundo quiere que 24.04.4 se marque OUTDATED solo por existir 26.04.

### Trabajo

- [ ] En catalog o CLI: `upgrade_policy: latest | same-series | latest-lts` (default `latest-lts` para Ubuntu server).
- [ ] Flag global `--policy same-series` para un check.
- [ ] Nota en tabla cuando hay LTS más nueva pero policy = same-series: no OUTDATED, status OK + note informativa opcional (`--hint-newer-lts`).

### Criterios de aceptación

```bash
uv run ventoy-iso-check check /mnt/e --only ubuntu --policy same-series
# 24.04.4 OK si el point-release está al día
uv run ventoy-iso-check check /mnt/e --only ubuntu --policy latest-lts
# 24.04.4 OUTDATED vs 26.04
```

---

## Fase 6 — Catálogo inteligente y más distros

**Estado:** `pending`  
**Estimación:** L  
**Depende de:** 1

### Objetivo

Menos `UNSUPPORTED` y menos fricción al añadir distros.

### Trabajo

- [ ] Comando `ventoy-iso-check suggest` → imprime snippet YAML para UNSUPPORTED.
- [ ] Añadir distros frecuentes si el usuario las tiene: Debian netinst, Arch, GParted, Memtest86+.
- [ ] Mejorar Zorin/pearOS (al menos página + version parse robusto).
- [ ] Documentar cómo contribuir un resolver en ARCHITECTURE.md (ya hay base).

### Criterios de aceptación

```bash
uv run ventoy-iso-check suggest /mnt/e
# output con bloques YAML válidos
```

---

## Fase 7 — Tests y rendimiento HTTP

**Estado:** `pending`  
**Estimación:** L  
**Depende de:** 3 (ideal)

### Trabajo

- [ ] `pytest` + fixtures HTML offline para Ubuntu/Fedora/Mint/Pop.
- [ ] Tests de `version_cmp` y match de catalog.
- [ ] Resolvers async o `ThreadPoolExecutor` con límite de concurrencia.
- [ ] `uv run pytest` en README/Makefile.

### Criterios de aceptación

```bash
uv run pytest -q
# check de 10 distros no tarda mucho más que 1 (orden de magnitud)
```

---

## Fase 8 — Export y Ventoy bootloader

**Estado:** `pending`  
**Estimación:** M  
**Depende de:** 1

### Trabajo

- [ ] `--format csv|html` o subcomando `export`.
- [ ] Check versión Ventoy en `Bootloaders/ventoy-*/ventoy/version` vs GitHub latest.
- [ ] Status aparte o sección en resumen (no mezclar con ISOs si confunde).

---

## Fase 9 — CI

**Estado:** `pending`  
**Estimación:** S–M  
**Depende de:** 7 (tests)

### Trabajo

- [ ] GitHub Actions: `uv sync`, `pytest`, `ruff` (si se añade), `docker build`.
- [ ] No montar discos reales en CI; solo unit tests.

---

## Orden de ejecución recomendado para agentes

```text
Fase 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
```

Si el usuario pide solo una mejora concreta, mapearla a la fase y **no** implementar fases posteriores de relleno.

## Prompt sugerido para reanudar trabajo

```text
Lee AGENTS.md y docs/PHASED_PLAN.md.
Ejecuta la siguiente fase pending en orden (o la fase N que indique).
No descargues ISOs reales. Verifica con uv. Commit y actualiza el plan.
```

## Registro de completadas

| Fase | completed_at | commit | Notas |
|------|--------------|--------|-------|
| 0 | 2026-07-24 | (baseline 0.3.0 + docs agentes) | Incluye fechas mtime, Docker, LTS fixes |

<!-- Los agentes añaden filas aquí -->
