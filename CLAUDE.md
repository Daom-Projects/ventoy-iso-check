# CLAUDE.md

Este proyecto usa instrucciones de agente unificadas.

**Leer primero:**

1. [AGENTS.md](./AGENTS.md) — reglas operativas para cualquier agente
2. [docs/CONTEXT.md](./docs/CONTEXT.md) — dominio Ventoy / ISOs / WSL
3. [docs/PHASED_PLAN.md](./docs/PHASED_PLAN.md) — roadmap por fases (ejecutar **una fase** a la vez)
4. [CHANGELOG.md](./CHANGELOG.md) — qué ya está entregado (baseline **v0.3.0**)

Stack: Python 3.12 + **uv**. CLI: `uv run ventoy-iso-check …`.  
Fase siguiente del plan: **1** (`--only-outdated` / `--only-stale`).  
No descargar ISOs salvo que el usuario lo pida. No borrar archivos del volumen Ventoy.
