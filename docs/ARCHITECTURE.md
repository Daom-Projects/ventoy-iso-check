# Arquitectura — ventoy-iso-check

## Flujo principal

```text
                    ┌─────────────────┐
                    │  CLI (Typer)    │
                    │ scan/check/     │
                    │ links/download  │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌────────────┐   ┌─────────────┐   ┌──────────────┐
    │ inventory  │   │  catalog    │   │ sisou_bridge │
    │ walk disk  │   │  YAML match │   │ download     │
    │ mtime/age  │   └──────┬──────┘   └──────────────┘
    └─────┬──────┘          │
          │                 ▼
          │          ┌─────────────┐
          └─────────►│  checker    │
                     │  + resolve  │
                     └──────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       resolvers.py   version_cmp   reporters
       (HTTP latest)  (outdated?)   Rich/JSON/MD
```

## Módulos

| Módulo | Responsabilidad |
|--------|-----------------|
| `cli.py` | Parsing args, defaults de path, orquestación de salida |
| `paths.py` | Resolución de raíz Ventoy y project root |
| `inventory.py` | Descubrimiento de `*.iso`/`*.img`, stats de archivo |
| `catalog.py` | Carga `catalog.yaml`, regex → entry + version local |
| `resolvers.py` | Consulta mirrors/páginas → `ResolveResult` |
| `version_cmp.py` | Normalización y `local < latest` |
| `checker.py` | Une inventario + resolve + `Status` |
| `reporters.py` | Tabla Rich, JSON, links.md |
| `sisou_bridge.py` | Materializa `sisou.toml` y lanza sisou/uv |
| `models.py` | Dataclasses y enums |

## Datos de configuración

| Archivo | Quién lo lee | Mutabilidad |
|---------|--------------|-------------|
| `catalog.yaml` | catalog.py | Humano / fase de catálogo |
| `sisou.toml` | sisou_bridge (plantilla) | Humano; `directory` reescrito en temp |
| `$VENTOY_ROOT` | paths / cli | Entorno |
| Futuro: `*.iso.meta.json` | inventory / download | Tool |

## Extender un resolver

```python
# resolvers.py
def resolve_midistro(entry: CatalogEntry, local_version: str | None) -> ResolveResult:
    ...
    return ResolveResult(latest_version="...", download_url="...", page="...")

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

## Docker

```text
builder (uv python 3.12) → venv + package + sisou
runtime (slim)           → ENTRYPOINT → ventoy-iso-check
volume                   → /ventoy = host Ventoy root
```

## Límites conocidos

- Resolvers síncronos (secuenciales) → check lento con muchas distros.
- Scraping HTML sin contratos estables.
- sisou y catalog pueden discrepar en nombres de archivo.
