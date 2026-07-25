# CLAUDE.md

Este proyecto usa instrucciones de agente unificadas.

**Leer primero:**

1. [AGENTS.md](./AGENTS.md) — reglas operativas para cualquier agente
2. [docs/CONTEXT.md](./docs/CONTEXT.md) — dominio Ventoy / ISOs / WSL
3. [docs/PHASED_PLAN.md](./docs/PHASED_PLAN.md) — roadmap por fases (ejecutar **una fase** a la vez)
4. [CHANGELOG.md](./CHANGELOG.md) — qué ya está entregado (**v1.0.0**)
5. [docs/WINDOWS.md](./docs/WINDOWS.md) — PowerShell / Docker / update Ventoy2Disk

Stack: Python 3.12 + **uv**. CLI Typer/Click + Rich: `uv run ventoy-iso-check …` o menú.  
Antes de commit: `uv run pytest -q` y `uv run ruff check src tests`.  
Plan de fases **0–9** + hito **1.0.0** completados.  
No descargar ISOs salvo que el usuario lo pida. No borrar archivos del volumen Ventoy.  
`ventoy --fetch` solo descarga paquetes a Bootloaders/; no reescribe MBR/ESP.
