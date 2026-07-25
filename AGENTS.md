# AGENTS.md — ventoy-iso-check

Instrucciones para agentes de código (Grok, Claude, Cursor, Codex, etc.) que trabajen en este repositorio.

## Proyecto en una frase

CLI Python (`uv`) + opcional Docker que **inventaría y comprueba ISOs** en un disco **Ventoy**, genera enlaces, y puede **descargar** vía SuperISOUpdater (`sisou`). Por defecto **no descarga**.

## Antes de tocar código

1. Leer `docs/CONTEXT.md` (arquitectura, layout del disco, convenciones).
2. Leer `docs/PHASED_PLAN.md` y trabajar **solo la fase activa** (o la que pida el usuario).
3. No borrar ISOs del disco del usuario (`/mnt/e`, `E:\`, etc.) salvo petición explícita.
4. Stack: **Python ≥3.12**, dependencias con **`uv`** (no pip suelto salvo Docker).
5. Repo: https://github.com/Daom-Projects/ventoy-iso-check · org `Daom-Projects` · licencia MIT.

## Comandos de verificación

```bash
cd ~/projects/ventoy-iso-check   # o el clone del agente
uv sync
uv run pytest -q
uv run ventoy-iso-check -V
uv run ventoy-iso-check scan /mnt/e --sort age          # si el volumen está montado
uv run ventoy-iso-check check /mnt/e --only fedora,ubuntu --workers 8
uv run ventoy-iso-check download /mnt/e --dry-run
docker build -t ventoy-iso-check:local .                # si tocas Docker
```

## Estructura relevante

```text
catalog.yaml                 # patrones ISO + managed_by + resolver
sisou.toml                   # plantilla SuperISOUpdater (directory se reescribe)
src/ventoy_iso_check/
  cli.py                     # Typer: scan | check | links | download
  inventory.py               # walk *.iso/*.img, mtime/age
  catalog.py                 # carga YAML + match regex
  resolvers.py               # latest remoto por distro
  version_cmp.py             # comparación de versiones
  checker.py                 # orquesta scan + resolve + status
  reporters.py               # Rich table, JSON, links.md
  sisou_bridge.py            # uv/sisou + TOML temporal
  paths.py                   # VENTOY_ROOT | /ventoy | /mnt/e
  models.py                  # IsoItem, Status, CatalogEntry
docs/
  CONTEXT.md                 # contexto profundo para agentes
  PHASED_PLAN.md             # plan por fases (fuente de verdad del roadmap)
  ARCHITECTURE.md            # diagrama de flujo y módulos
```

## Reglas de diseño (no negociables sin acuerdo)

| Regla | Motivo |
|-------|--------|
| `check`/`scan`/`links` nunca descargan | Seguridad y control del usuario |
| `download` solo vía sisou (o catálogo futuro explícito) | Un solo camino de escritura de ISOs |
| Status: OK / OUTDATED / UNKNOWN / MANUAL / UNSUPPORTED / ERROR | UX estable |
| Resolvers: preferir **última release publicada** (no anclar a major local) | Evitar falsos OK (Fedora 43 vs 44, Ubuntu LTS) |
| MediCat y árboles pesados fuera del scan salvo `--deep` | Rendimiento en 9p/USB |
| No commitear secretos, ISOs, ni `.venv` | Repo limpio |

## Cómo implementar una fase del plan

1. Abrir `docs/PHASED_PLAN.md` → sección de la fase.
2. Marcar la fase `in_progress` en el frontmatter/checklist del plan.
3. Implementar criterios de aceptación (tests o comandos de verificación listados).
4. Actualizar README solo si cambia la UX pública.
5. `uv sync` + comandos de verificación.
6. Commit convencional + push a `main` (o PR si la org lo exige):
   - `feat:` / `fix:` / `docs:` / `refactor:` / `test:`
7. Marcar la fase `done` y anotar fecha + commit en PHASED_PLAN.

## Estilo de código

- Type hints, Python 3.12+.
- Preferir módulos pequeños; resolvers nuevos en `resolvers.py` + entrada en `catalog.yaml` + `RESOLVERS`.
- Mensajes de CLI y notas de usuario en **español** (el README y la CLI ya lo están).
- Identificadores de código en inglés (`managed_by`, `stale_days`, …).

## Entorno del autor (contexto real)

- WSL2 en Windows 11; disco Ventoy en **`/mnt/e`** (drvfs/9p, ~232 GB).
- Layout: `Linux/`, `Herramientas/`, `Windows/`, a veces `tools/`.
- `uv` en PATH; Docker disponible.
- Organización GitHub: **Daom-Projects**.

## Qué no hacer

- No ejecutar `download` real sin confirmación del usuario (ISOs grandes, poco espacio).
- No “arreglar” MiniOS/Strelec/MediCat con auto-update.
- No hardcodear solo `/mnt/e` en lógica nueva: usar `paths.default_ventoy_root()` / `$VENTOY_ROOT`.
- No añadir dependencias pesadas sin justificarlas en la fase.

## Documentos relacionados

| Archivo | Uso |
|---------|-----|
| [docs/CONTEXT.md](docs/CONTEXT.md) | Contexto de dominio y decisiones |
| [docs/PHASED_PLAN.md](docs/PHASED_PLAN.md) | **Plan ejecutable por fases** (siguiente: Fase 1) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Flujos y módulos |
| [docs/README.md](docs/README.md) | Índice de docs internas |
| [README.md](README.md) | Usuario final |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo contribuir |
| [CLAUDE.md](CLAUDE.md) | Puntero para Claude Code |

## Versión actual

- Paquete: **0.10.0** (`pyproject.toml`, `src/ventoy_iso_check/__init__.py`)
- Fase del plan activa: **8** (export + Ventoy bootloader)
- Fases hechas: 0–7
