# Probar ventoy-iso-check desde Windows (PowerShell)

El disco Ventoy suele ser **`E:\`**. En WSL a veces `/mnt/e` queda descolgado; desde PowerShell nativo o Docker Desktop puedes probar sin depender de eso.

## Opción A — Docker Desktop (recomendada en Windows)

Requisitos: [Docker Desktop](https://www.docker.com/products/docker-desktop/) con integración WSL2 opcional.

```powershell
# Clonar / actualizar
cd $env:USERPROFILE\projects   # o la ruta que uses
# Si el repo solo está en WSL:
#   wsl -e bash -lc "cd ~/projects/ventoy-iso-check && git pull"
# O clona en Windows:
git clone https://github.com/Daom-Projects/ventoy-iso-check.git
cd ventoy-iso-check
git pull

docker build -t ventoy-iso-check:local .

# Inventario (monta E:\ como /ventoy dentro del contenedor)
docker run --rm -v E:\:/ventoy ventoy-iso-check:local scan

# Check + filtros Fase 1
docker run --rm -v E:\:/ventoy ventoy-iso-check:local check --only-outdated --urls
docker run --rm -v E:\:/ventoy ventoy-iso-check:local scan --only-stale --stale-days 90 --sort age

# Espacio libre (Fase 2) — dry-run de download
docker run --rm -v E:\:/ventoy ventoy-iso-check:local download --dry-run

# Forzar si el libre es muy bajo (no recomendado)
docker run --rm -v E:\:/ventoy ventoy-iso-check:local download --dry-run --force
```

**Nota:** en PowerShell la barra final `E:\:` evita ambigüedades de parsing. Si falla el mount, en Docker Desktop → Settings → Resources → File sharing asegúrate de compartir la unidad `E:`.

### docker compose desde PowerShell

```powershell
cd path\to\ventoy-iso-check
$env:VENTOY_HOST = "E:\"
docker compose run --rm vic scan
docker compose run --rm vic check --only-actionable
docker compose run --rm vic download --dry-run
```

---

## Opción B — uv / Python nativo en Windows

```powershell
# Instalar uv (una vez): https://docs.astral.sh/uv/
# winget install astral-sh.uv   # o el método de la web

cd path\to\ventoy-iso-check
git pull
uv sync

# Raíz del Ventoy en Windows
$env:VENTOY_ROOT = "E:\"

uv run ventoy-iso-check -V
uv run ventoy-iso-check scan
uv run ventoy-iso-check check --only-outdated --urls
uv run ventoy-iso-check scan --only-stale --stale-days 90 --sort age
uv run ventoy-iso-check download --dry-run
```

`download` real en Windows nativo usa `uv tool run --python 3.12 sisou@latest …` (igual que en WSL).

---

## Opción C — Invocar WSL desde PowerShell

Si el código vive en el home de Ubuntu y `/mnt/e` está bien montado:

```powershell
# Remount / reinicio si /mnt/e falla
wsl --shutdown
# Abre de nuevo la terminal WSL o:
wsl -e bash -lc "ls /mnt/e/Linux | head"

wsl -e bash -lc "cd ~/projects/ventoy-iso-check && git pull && uv sync && uv run ventoy-iso-check scan /mnt/e --sort age"
wsl -e bash -lc "cd ~/projects/ventoy-iso-check && uv run ventoy-iso-check check /mnt/e --only-outdated --urls"
wsl -e bash -lc "cd ~/projects/ventoy-iso-check && uv run ventoy-iso-check download /mnt/e --dry-run"
```

Si `ls /mnt/e` dice *No such device* pero `E:\` funciona en el Explorador:

```powershell
wsl --shutdown
# Vuelve a abrir WSL; o en una shell WSL con permisos:
#   sudo mount -t drvfs E: /mnt/e
```

---

## Comprobar espacio libre sin la tool

```powershell
Get-Volume -DriveLetter E |
  Select-Object DriveLetter, FileSystemLabel,
    @{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,2)}},
    @{N='TotalGB';E={[math]::Round($_.Size/1GB,2)}}
```

---

## Qué probar tras cada fase

| Fase | Comando típico (Docker) |
|------|-------------------------|
| 1 filtros | `… check --only-outdated` / `… scan --only-stale --stale-days 90` |
| 2 espacio | `… download --dry-run` (debe mostrar GiB libres) |
| 3 cache | dos `check` seguidos; el 2º más rápido |
| 4 meta | sidecar junto a una ISO tras download |

---

## Errores frecuentes

| Síntoma | Qué hacer |
|---------|-----------|
| `No such device` en `/mnt/e` | `wsl --shutdown` o montar `E:` con Docker |
| Docker no ve `E:\` | File sharing / reinsertar USB |
| `uv` no encontrado en PowerShell | Instalar uv o usar Docker |
| sisou / libtorrent en Windows | Preferir Docker o Python 3.12 en PATH |
