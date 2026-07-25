# Arquitectura — ventoy-iso-check

## Flujo principal

```text
                    ┌─────────────────┐
                    │  CLI (Typer)    │
                    │ scan/check/     │
                    │ links/download  │
                    │ meta/suggest    │
                    └────────┬────────┘
                             │
     ┌───────────┬───────────┼───────────┬────────────┐
     ▼           ▼           ▼           ▼            ▼
 inventory   catalog     cache      filters      sisou_bridge
 walk disk   YAML match  latest     UX filter    download
 mtime/meta              TTL
     │           │
     └─────┬─────┘
           ▼
        checker (+ policy + resolve + checksum)
           │
     ┌─────┴─────┬──────────┐
     ▼           ▼          ▼
 resolvers   version_cmp  reporters
 HTTP        outdated?    Rich/JSON/MD
```

## Módulos

| Módulo | Responsabilidad |
|--------|-----------------|
| `cli.py` | Typer: scan, check, links, download, meta, suggest |
| `paths.py` | Raíz Ventoy y project root |
| `inventory.py` | `*.iso`/`*.img`, mtime, sidecars |
| `catalog.py` | `catalog.yaml` + regex → entry/version |
| `suggest.py` | YAML sugerido para UNSUPPORTED |
| `resolvers.py` | Latest remoto por distro |
| `policy.py` | `latest` / `latest-lts` / `same-series` |
| `version_cmp.py` | Comparación de versiones |
| `checker.py` | Orquesta status |
| `filters.py` | only-outdated / stale / actionable |
| `cache.py` | Cache JSON de latest |
| `meta.py` | Sidecars `.meta.json` + SHA-256 |
| `disk.py` | Espacio libre pre-download |
| `reporters.py` | Tabla / JSON / links.md |
| `sisou_bridge.py` | sisou + seal post-download |
| `models.py` | Dataclasses y enums |

## Datos de configuración

| Archivo | Quién lo lee | Mutabilidad |
|---------|--------------|-------------|
| `catalog.yaml` | catalog.py | Humano / `suggest` |
| `sisou.toml` | sisou_bridge | Humano; `directory` temporal |
| `$VENTOY_ROOT` | paths / cli | Entorno |
| `*.iso.meta.json` | meta / inventory | Tool / `meta seal` |
| `~/.cache/ventoy-iso-check/latest.json` | cache.py | Tool |

## Extender el catálogo (checklist)

1. **Detectar** la ISO en el USB (`scan`) → si sale `UNSUPPORTED`, usar `suggest`.
2. **Añadir entrada** en `catalog.yaml` (o pegar el YAML de `suggest` y editar).
3. **Elegir `managed_by`:**
   - `sisou` — si SuperISOUpdater tiene updater (y bloque en `sisou.toml`)
   - `catalog` — resolver propio en `resolvers.py`
   - `manual` — solo inventario + página
4. **Resolver (si `catalog`):**

```python
# resolvers.py
def resolve_midistro(
    entry: CatalogEntry,
    local_version: str | None,
    # opcional policy-aware:
    # *, policy: UpgradePolicy = UpgradePolicy.LATEST_LTS, hint_newer: bool = False,
) -> ResolveResult:
    ...
    return ResolveResult(
        latest_version="1.2.3",
        download_url="https://...",
        page="https://...",
    )

RESOLVERS["midistro"] = resolve_midistro
```

```yaml
# catalog.yaml
- id: midistro
  label: Mi Distro
  patterns:
    - '(?i)^midistro-(\d+\.\d+)\.iso$'
  managed_by: catalog
  resolver: midistro
  page: https://example.com/
```

5. Si el resolver respeta multi-LTS, registrarlo en `policy.POLICY_AWARE_RESOLVERS`.
6. Probar:

```bash
uv run ventoy-iso-check check "$VENTOY_ROOT" --only midistro --no-cache
uv run ventoy-iso-check suggest "$VENTOY_ROOT"
```

## Docker

```text
builder (uv python 3.12) → venv + package + sisou
runtime (slim)           → ENTRYPOINT → ventoy-iso-check
volume                   → /ventoy = host Ventoy root
```

## Límites conocidos

- Resolvers mayormente síncronos (cache mitiga re-scrape).
- Scraping HTML sin contratos estables.
- sisou y catalog pueden discrepar en nombres de archivo.
- `suggest` genera plantillas; hay que revisar `page` / `resolver` a mano.
