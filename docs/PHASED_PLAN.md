---
title: Plan de mejoras por fases
project: ventoy-iso-check
status: active
last_updated: 2026-07-25
current_phase: 4
version_baseline: "0.6.0"
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
| 1 | Filtros UX (`--only-outdated`, `--only-stale`) | **done** | Alta |
| 2 | Pre-check de espacio libre en `download` | **done** | Alta |
| 3 | Cache de latest (TTL) | **done** | Alta |
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
- sisou bridge + Docker multiplataforma
- File date / Age (`mtime`) + `--sort` / `--stale-days`
- Docs agentes: `AGENTS.md`, `CLAUDE.md`, `docs/*`, Copilot instructions
- `CHANGELOG.md`, `CONTRIBUTING.md`

**Commits de referencia:** `51631e0` (0.1 portable) → `0ca3b37` (0.3 fechas) → docs agentes `f2d4910`+

**Verificación:** `uv run ventoy-iso-check scan $VENTOY_ROOT --sort age`


---

## Fase 1 — Filtros UX

**Estado:** `done` (2026-07-25, v0.4.0)  
**Estimación:** S / 1 sesión  
**Depende de:** 0

### Objetivo

Que el usuario vea solo lo accionable sin scroll de MiniOS/XP.

### Trabajo

- [x] Flag `--only-outdated` en `check`/`links` (status == OUTDATED).
- [x] Flag `--only-stale` (age_days ≥ `--stale-days`).
- [x] Combinables con `--only id1,id2`.
- [x] `--only-actionable` = OUTDATED | ERROR | stale.
- [x] Documentar en README / CHANGELOG.
- [x] Módulo `filters.py`.

### Criterios de aceptación

```bash
uv run ventoy-iso-check check /mnt/e --only-outdated
# solo filas OUTDATED (o mensaje "ninguna")
uv run ventoy-iso-check scan /mnt/e --only-stale --stale-days 90 --sort age
```

### Notas de implementación

Filtrar **después** de `run_check`. El filtro aplica también al JSON exportado.

---

## Fase 2 — Espacio libre antes de download

**Estado:** `done` (2026-07-25, v0.5.0)  
**Estimación:** S  
**Depende de:** 0

### Objetivo

Evitar descargas a medias cuando el USB no tiene espacio.

### Trabajo

- [x] Función `disk_usage(ventoy_root)` (`disk.py` + `shutil.disk_usage`).
- [x] En `download` (antes de sisou): mostrar free/total.
- [x] WARN si free < `--warn-gib` (default 8); ABORT si free < `--abort-gib` (default 2) salvo `--force`.
- [ ] Opcional (futuro): estimar tamaño de updaters enabled.

### Criterios de aceptación

```bash
uv run ventoy-iso-check download /mnt/e --dry-run
# imprime espacio libre
uv run ventoy-iso-check download /mnt/e --dry-run --abort-gib 99999
# exit 3 sin --force
```

---

## Fase 3 — Cache de latest

**Estado:** `done` (2026-07-25, v0.6.0)  
**Estimación:** M  
**Depende de:** 0

### Objetivo

`check` rápido en WSL sin re-scrape cada vez.

### Trabajo

- [x] Cache en `~/.cache/ventoy-iso-check/latest.json` (o `$XDG_CACHE_HOME` / `--cache-dir`).
- [x] Clave: `catalog_id|resolver|edition|arch|local_version`.
- [x] TTL default 12 h; flags `--no-cache`, `--refresh`, `--ttl-hours`.
- [x] Guardar `ResolveResult` serializable + `fetched_at`.
- [x] Stats hits/misses en consola; README.

### Criterios de aceptación

```bash
time uv run ventoy-iso-check check /mnt/e --only ubuntu,fedora
time uv run ventoy-iso-check check /mnt/e --only ubuntu,fedora   # 2ª vez mucho más rápida
uv run ventoy-iso-check check /mnt/e --refresh --only ubuntu
```

### No hacer

Cachear en el USB por defecto (lento/sucio); opcional `--cache-dir` sí.

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
| 0 | 2026-07-24 | `0ca3b37` / `f2d4910` | Baseline 0.3.0: fechas mtime, Docker, LTS/Fedora fixes, docs agentes |
| 1 | 2026-07-25 | (v0.4.0) | `--only-outdated` / `--only-stale` / `--only-actionable`; catálogo elementary, virtio, mint mate |
| 2 | 2026-07-25 | (v0.5.0) | Espacio libre pre-download; docs/WINDOWS.md |
| 3 | 2026-07-25 | (v0.6.0) | Cache latest TTL 12h; validación fases 1–2 en /mnt/e |

<!-- Los agentes añaden filas aquí al completar fases -->
