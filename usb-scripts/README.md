# Scripts para ejecutar ventoy-iso-check desde el USB

Layout recomendado en el disco Ventoy:

```text
E:\   (o /mnt/e)
├── Bootloaders\          # Ventoy, Rufus, balenaEtcher, …
├── Linux\
├── Herramientas\
├── Windows\
└── Scripts\
    ├── Run-VentoyIsoCheck.ps1   ← acceso rápido (opcional, copia)
    └── ventoy-iso-check\        ← clon del repositorio
        ├── Dockerfile
        ├── usb-scripts\
        │   ├── Run-VentoyIsoCheck.ps1
        │   └── run-ventoy-iso-check.sh
        └── …
```

## Requisito: Docker

Los lanzadores **comprueban Docker** y **no ejecutan** la herramienta si:

- `docker` no está en el PATH, o
- el daemon no responde (Docker Desktop apagado).

Código de salida `3` = Docker no disponible.

## Windows (PowerShell)

```powershell
# Primera vez: clonar (si aún no está)
cd E:\Scripts
git clone https://github.com/Daom-Projects/ventoy-iso-check.git

# Ejecutar (acceso directo recomendado)
cd E:\Scripts\ventoy-iso-check\usb-scripts
.\Run-VentoyIsoCheck.ps1
.\Run-VentoyIsoCheck.ps1 check --only-outdated --urls
.\Run-VentoyIsoCheck.ps1 bootloaders
.\Run-VentoyIsoCheck.ps1 ventoy
.\Run-VentoyIsoCheck.ps1 -Rebuild   # reconstruir imagen Docker
```

Si PowerShell bloquea scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# o:
powershell -ExecutionPolicy Bypass -File .\Run-VentoyIsoCheck.ps1 scan
```

Copia opcional al padre para un solo click:

```powershell
Copy-Item E:\Scripts\ventoy-iso-check\usb-scripts\Run-VentoyIsoCheck.ps1 E:\Scripts\
```

## WSL / Linux

```bash
cd /mnt/e/Scripts/ventoy-iso-check/usb-scripts
chmod +x run-ventoy-iso-check.sh
./run-ventoy-iso-check.sh
./run-ventoy-iso-check.sh check --only-outdated --urls
./run-ventoy-iso-check.sh bootloaders
REBUILD=1 ./run-ventoy-iso-check.sh scan
```

Sin Docker, en el host con `uv`:

```bash
cd /mnt/e/Scripts/ventoy-iso-check
uv sync
export VENTOY_ROOT=/mnt/e
uv run ventoy-iso-check scan --sort age
```

## Actualizar el clon en el USB

```powershell
cd E:\Scripts\ventoy-iso-check
git pull
.\usb-scripts\Run-VentoyIsoCheck.ps1 -Rebuild
```

## Nota sobre el menú interactivo

`-Menu` / `menu` usa prompts Rich. En `docker run -it` funciona mejor en terminal real (Windows Terminal / WSL). En algunos hosts sin TTY el menú se desactiva y hay que usar subcomandos.
