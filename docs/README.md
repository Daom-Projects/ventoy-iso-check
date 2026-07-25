# Documentación interna

Índice de docs del proyecto **ventoy-iso-check** (v0.12.0).

| Documento | Audiencia | Contenido |
|-----------|-----------|-----------|
| [../README.md](../README.md) | Usuario final | Instalación, CLI, Docker, cobertura |
| [../CHANGELOG.md](../CHANGELOG.md) | Todos | Historial de versiones |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Humanos + agentes | Cómo contribuir + CI |
| [../AGENTS.md](../AGENTS.md) | Agentes de código | Reglas operativas |
| [../CLAUDE.md](../CLAUDE.md) | Claude Code | Puntero a AGENTS |
| [CONTEXT.md](./CONTEXT.md) | Agentes | Dominio Ventoy / WSL / decisiones |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Agentes | Flujos y módulos |
| [PHASED_PLAN.md](./PHASED_PLAN.md) | Agentes + humano | Plan por fases (**0–9 done**) |
| [WINDOWS.md](./WINDOWS.md) | Usuario Windows | PowerShell / Docker / WSL |

## Continuar desarrollo

El roadmap de fases 0–9 está **completo**. Para trabajo nuevo:

```text
Lee AGENTS.md y docs/PHASED_PLAN.md.
Implementa la mejora pedida (issue / pedido del usuario).
No descargues ISOs reales. Verifica con uv + pytest. Commit y push.
```

CI en cada push/PR: `.github/workflows/ci.yml` (pytest + docker build, sin discos).
