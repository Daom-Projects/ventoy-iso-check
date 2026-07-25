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

## Recomendado en Windows: uv nativo (sin Docker)

El lanzador **por defecto** usa **Python/uv en Windows** y lee el USB
directamente (`E:\`, `F:\`, …). No necesita Docker ni WSL.

```powershell
cd E:\Scripts
.\Run-VentoyIsoCheck.ps1
# o:
.\ventoy-iso-check\usb-scripts\Run-VentoyIsoCheck.ps1 scan
```

Requisitos:

1. [uv](https://docs.astral.sh/uv/) (el script intenta instalarlo; o `winget install astral-sh.uv`)
2. Opcional: Git for Windows (si no, copia el repo a `%USERPROFILE%\projects\ventoy-iso-check`)

El código y `.venv` se crean en **`%USERPROFILE%\projects\ventoy-iso-check`**
(disco C:), no en el USB (evita errores de permisos).

```powershell
$env:VENTOY_ROOT = "E:\"
cd $env:USERPROFILE\projects\ventoy-iso-check
uv sync
uv run ventoy-iso-check menu
uv run ventoy-iso-check scan
uv run ventoy-iso-check check --only-outdated --urls
```

Motores:

| `-Engine` | Uso |
|-----------|-----|
| **Native** (default) | uv en Windows + `E:\` |
| Wsl | uv en WSL + `/mnt/e` |
| Docker | imagen local (falla a menudo con USB extraíble) |
| Auto | Native, luego WSL |

## Windows (PowerShell)

```powershell
# Primera vez: clonar (si aún no está)
cd E:\Scripts
git clone https://github.com/Daom-Projects/ventoy-iso-check.git
# o: .\UPDATE-FROM-GITHUB.ps1

# Ejecutar — SIN argumentos abre el MENÚ
cd E:\Scripts
.\Run-VentoyIsoCheck.ps1

# O con subcomandos
.\Run-VentoyIsoCheck.ps1 check --only-outdated --urls
.\Run-VentoyIsoCheck.ps1 bootloaders
.\Run-VentoyIsoCheck.ps1 scan --sort age
.\Run-VentoyIsoCheck.ps1 -Rebuild   # reconstruir imagen Docker
```

### Unidad distinta a E:

El script detecta la letra del USB solo. Si hace falta forzarla:

```powershell
.\Run-VentoyIsoCheck.ps1 -Drive F
.\Run-VentoyIsoCheck.ps1 -Drive D scan
```

### Error `sh\r` / `env: 'sh\r'`

Línea Windows (CRLF) en el entrypoint. Reconstruir:

```powershell
.\Run-VentoyIsoCheck.ps1 -Rebuild
```

### Si sale `total=0` ISOs (montaje Docker vacío)

Es el fallo más habitual con **USB + Docker Desktop (WSL2)**: el menú arranca pero `/ventoy` dentro del contenedor está vacío.

El lanzador en modo **Auto**:

1. Intenta Docker con varios tipos de montaje.
2. Si no ve ISOs → **fallback a WSL + uv** (`VENTOY_ROOT=/mnt/e`), que suele ver el USB bien.

Forzar un motor:

```powershell
.\Run-VentoyIsoCheck.ps1 -Engine Wsl      # recomendado si Docker no monta el USB
.\Run-VentoyIsoCheck.ps1 -Engine Docker  # solo Docker
```

Requisitos del fallback WSL:

- WSL instalado y la unidad visible: `wsl -e ls /mnt/e/Linux`
- `uv` en WSL (el script intenta instalarlo si falta)
- Repo en `/mnt/e/Scripts/ventoy-iso-check` o `~/projects/ventoy-iso-check`

File sharing de Docker (solo si quieres Docker puro):

1. Docker Desktop → **Settings → Resources → File sharing** → marca **E:** (u otra).
2. Apply & Restart.
3. `.\Run-VentoyIsoCheck.ps1 -Engine Docker`

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
