# Contribuir

Gracias por mejorar **ventoy-iso-check**.

## Para humanos

1. Fork / branch desde `main`.
2. `uv sync`
3. Cambios + verificación local (ver abajo).
4. PR o push según el flujo de la org [Daom-Projects](https://github.com/Daom-Projects).

## Para agentes de código

Sigue **[AGENTS.md](./AGENTS.md)** y ejecuta **una fase** de **[docs/PHASED_PLAN.md](./docs/PHASED_PLAN.md)** por sesión salvo instrucción contraria.

## Verificación mínima

```bash
uv sync
uv run ventoy-iso-check -V
uv run ventoy-iso-check scan --help
# Con volumen montado (opcional):
# uv run ventoy-iso-check scan "$VENTOY_ROOT" --sort age
```

Si tocas Docker:

```bash
docker build -t ventoy-iso-check:local .
```

## Convenciones

| Tema | Convención |
|------|------------|
| Commits | Conventional Commits (`feat:`, `fix:`, `docs:`, …) |
| Python | ≥ 3.12, tipos, sin dependencias nuevas sin justificación |
| Empaquetado | **uv** (`uv sync`, `uv run`, `uv lock`) |
| UI / notas al usuario | Español |
| Identificadores de código | Inglés |
| Descargas reales de ISO | Solo con petición explícita del usuario |

## Añadir una distro

1. Entrada en `catalog.yaml` (`patterns`, `managed_by`, `resolver` o `manual`).
2. Si hay fuente estable: función en `resolvers.py` + clave en `RESOLVERS`.
3. Si SuperISOUpdater la soporta: bloque en `sisou.toml`.
4. Probar: `uv run ventoy-iso-check check "$VENTOY_ROOT" --only <id>`.

Detalle: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md), [docs/CONTEXT.md](./docs/CONTEXT.md).

## Licencia

Al contribuir aceptas que el código se publique bajo **MIT** (ver `LICENSE`).  
SISOU es un proyecto de terceros (GPL-2.0-or-later).
