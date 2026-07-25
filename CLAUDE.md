# CLAUDE.md

Este proyecto usa instrucciones de agente unificadas.

**Leer primero:**

1. [AGENTS.md](./AGENTS.md) — reglas operativas para cualquier agente
2. [docs/CONTEXT.md](./docs/CONTEXT.md) — dominio Ventoy / ISOs / WSL
3. [docs/PHASED_PLAN.md](./docs/PHASED_PLAN.md) — roadmap por fases (ejecutar **una fase** a la vez)
4. [CHANGELOG.md](./CHANGELOG.md) — qué ya está entregado (**v0.10.0**)
5. [docs/WINDOWS.md](./docs/WINDOWS.md) — probar desde PowerShell / Docker Desktop

Stack: Python 3.12 + **uv**. CLI: `uv run ventoy-iso-check …`.  
Antes de commit: `uv run pytest -q`.  
Fase siguiente del plan: **8** (export CSV/HTML + check Ventoy).  
No descargar ISOs salvo que el usuario lo pida. No borrar archivos del volumen Ventoy.
