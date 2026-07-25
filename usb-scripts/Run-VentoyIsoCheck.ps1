#Requires -Version 5.1
<#
.SYNOPSIS
  Lanza ventoy-iso-check desde el USB Ventoy (Windows).

.DESCRIPTION
  Por defecto usa Python/uv NATIVO en Windows (sin Docker, sin WSL).
  Accede a E:\ (o la letra del USB) directamente.

  El codigo y el .venv viven en:
    %USERPROFILE%\projects\ventoy-iso-check
  (disco del sistema; el USB solo aporta las ISOs via VENTOY_ROOT).

.EXAMPLE
  .\Run-VentoyIsoCheck.ps1
  .\Run-VentoyIsoCheck.ps1 scan
  .\Run-VentoyIsoCheck.ps1 check --only-outdated --urls
  .\Run-VentoyIsoCheck.ps1 bootloaders
  .\Run-VentoyIsoCheck.ps1 -Engine Wsl
  .\Run-VentoyIsoCheck.ps1 -Drive F
#>
[CmdletBinding()]
param(
    [switch]$Menu,
    [switch]$Rebuild,
    [switch]$NoMenu,
    # Native = uv en Windows (recomendado) | Wsl | Docker | Auto
    [ValidateSet("Native", "Wsl", "Docker", "Auto")]
    [string]$Engine = "Native",
    [string]$Drive = "",
    [string]$Image = "ventoy-iso-check:local",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

Set-StrictMode -Version Latest
# Continue: uv escribe progreso a stderr y con "Stop" PowerShell lo trata como error fatal
$ErrorActionPreference = "Continue"

function Write-Info([string]$msg) { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Cyan }
function Write-Warn([string]$msg) { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Red }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$GitUrl = "https://github.com/Daom-Projects/ventoy-iso-check.git"
$WinRepo = Join-Path $env:USERPROFILE "projects\ventoy-iso-check"

# --- Localizar repo en USB (solo para detectar letra de unidad / Docker build) ---
$UsbRepo = $null
if (Test-Path (Join-Path $ScriptDir "Dockerfile")) {
    $UsbRepo = $ScriptDir
} elseif (Test-Path (Join-Path (Split-Path $ScriptDir -Parent) "Dockerfile")) {
    $UsbRepo = (Resolve-Path (Split-Path $ScriptDir -Parent)).Path
} elseif (Test-Path (Join-Path $ScriptDir "ventoy-iso-check\Dockerfile")) {
    $UsbRepo = (Resolve-Path (Join-Path $ScriptDir "ventoy-iso-check")).Path
}

# --- Letra del USB ---
if ($Drive) {
    $DriveLetter = $Drive.Trim().TrimEnd(':').TrimEnd('\').ToUpper()
} elseif ($UsbRepo) {
    $DriveRoot = (Get-Item $UsbRepo).PSDrive.Root
    if (-not $DriveRoot) { $DriveRoot = [System.IO.Path]::GetPathRoot($UsbRepo) }
    $DriveLetter = $DriveRoot.TrimEnd('\').TrimEnd(':').ToUpper()
} else {
    # Si el script esta en E:\Scripts\, usar esa unidad
    $DriveRoot = (Get-Item $ScriptDir).PSDrive.Root
    $DriveLetter = $DriveRoot.TrimEnd('\').TrimEnd(':').ToUpper()
}

if (-not $DriveLetter -or $DriveLetter.Length -ne 1) {
    Write-Err "No se detecto la letra del USB. Usa: -Drive E"
    exit 2
}

$VentoyRoot = "${DriveLetter}:\"
if (-not (Test-Path $VentoyRoot)) {
    Write-Err "La unidad ${DriveLetter}: no existe."
    exit 2
}

# Argumentos CLI
if ($Menu) {
    $AppArgs = @("menu")
} elseif ($CliArgs -and $CliArgs.Count -gt 0) {
    $AppArgs = @($CliArgs)
} elseif ($NoMenu) {
    $AppArgs = @("scan", "--sort", "age")
} else {
    $AppArgs = @("menu")
}

Write-Info "Ventoy:  $VentoyRoot"
Write-Info "Engine:  $Engine"
Write-Info "Args:    $($AppArgs -join ' ')"
Write-Info "WinRepo: $WinRepo"

$hostIso = @(Get-ChildItem -Path (Join-Path $VentoyRoot "Linux") -Filter *.iso -ErrorAction SilentlyContinue).Count
$hostIso += @(Get-ChildItem -Path (Join-Path $VentoyRoot "Herramientas") -Filter *.iso -ErrorAction SilentlyContinue).Count
Write-Info "Host:    $hostIso ISO(s) en Linux/ + Herramientas/"

# =====================================================================
# Native Windows: uv + Python del PC, acceso directo a E:\
# =====================================================================
function Install-UvWindows {
    if (Get-Command uv -ErrorAction SilentlyContinue) { return $true }

    $uvLocal = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $uvLocal) {
        $env:Path = "$(Split-Path $uvLocal);$env:Path"
        if (Get-Command uv -ErrorAction SilentlyContinue) { return $true }
    }

    Write-Info "uv no esta en PATH. Intentando instalar (oficial)..."
    try {
        # Instalador oficial Astral (no requiere admin)
        irm https://astral.sh/uv/install.ps1 | iex
    } catch {
        Write-Warn "install.ps1 fallo: $_"
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin"),
        (Join-Path $env:USERPROFILE ".cargo\bin"),
        (Join-Path $env:LOCALAPPDATA "uv\bin")
    )
    foreach ($d in $candidates) {
        if (Test-Path (Join-Path $d "uv.exe")) {
            $env:Path = "$d;$env:Path"
            break
        }
    }

    if (Get-Command uv -ErrorAction SilentlyContinue) { return $true }

    Write-Err "No se pudo instalar uv automaticamente."
    Write-Err "Opciones:"
    Write-Err "  1) winget install astral-sh.uv"
    Write-Err "  2) https://docs.astral.sh/uv/getting-started/installation/"
    Write-Err "  3) Cierra y reabre PowerShell tras instalar"
    return $false
}

function Ensure-WinRepo {
    $parent = Split-Path $WinRepo -Parent
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    if (-not (Test-Path (Join-Path $WinRepo "pyproject.toml"))) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Err "git no esta en PATH. Instala Git for Windows o copia el repo a:"
            Write-Err "  $WinRepo"
            if ($UsbRepo -and (Test-Path (Join-Path $UsbRepo "pyproject.toml"))) {
                Write-Info "Copiando desde USB (sin .venv)..."
                New-Item -ItemType Directory -Path $WinRepo -Force | Out-Null
                # Robocopy excluyendo basura
                & robocopy $UsbRepo $WinRepo /E /XD .venv .git __pycache__ .mypy_cache .ruff_cache .pytest_cache /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
                if (-not (Test-Path (Join-Path $WinRepo "pyproject.toml"))) {
                    return $false
                }
                return $true
            }
            return $false
        }
        Write-Info "Clonando $GitUrl -> $WinRepo"
        git clone --depth 1 $GitUrl $WinRepo
    } else {
        if (Test-Path (Join-Path $WinRepo ".git")) {
            Write-Info "Actualizando $WinRepo (git pull)..."
            Push-Location $WinRepo
            try { git pull --ff-only 2>$null } catch { }
            finally { Pop-Location }
        }
    }
    return (Test-Path (Join-Path $WinRepo "pyproject.toml"))
}

function Invoke-NativeEngine {
    Write-Info "=== Motor Native (Windows + uv, sin Docker) ==="

    if (-not (Install-UvWindows)) { return 3 }
    $uvVer = & uv --version 2>&1
    Write-Info "uv: $uvVer"

    if (-not (Ensure-WinRepo)) {
        Write-Err "No hay repo en $WinRepo"
        return 2
    }

    $env:VENTOY_ROOT = $VentoyRoot.TrimEnd('\') + '\'
    # Forzar menú/prompts aunque uv/PowerShell no reporten isatty()
    $env:VENTOY_ISO_CHECK_INTERACTIVE = "1"
    $env:PYTHONUNBUFFERED = "1"
    $env:UV_LINK_MODE = "copy"

    Push-Location $WinRepo
    try {
        # git pull por si el clon es viejo
        if (Test-Path (Join-Path $WinRepo ".git")) {
            Write-Info "git pull en $WinRepo ..."
            $null = & git -C $WinRepo pull --ff-only 2>&1
        }

        Write-Info "uv sync en $WinRepo ..."
        # uv imprime a stderr; no redirigir de forma que rompa con $ErrorActionPreference
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        try {
            & uv sync
            $syncCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prevEap
        }
        if ($syncCode -ne 0) {
            Write-Err "uv sync fallo (codigo $syncCode)"
            return $syncCode
        }

        Write-Info "VENTOY_ROOT=$env:VENTOY_ROOT"
        Write-Info "VENTOY_ISO_CHECK_INTERACTIVE=$env:VENTOY_ISO_CHECK_INTERACTIVE"
        Write-Info "uv run ventoy-iso-check $($AppArgs -join ' ')"

        # Lanzar proceso hijo heredando la consola (evita falsos "no TTY")
        $ErrorActionPreference = "SilentlyContinue"
        try {
            & uv run ventoy-iso-check @AppArgs
            return $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prevEap
        }
    } finally {
        Pop-Location
    }
}

# =====================================================================
# WSL (con TTY interactivo)
# =====================================================================
function Invoke-WslEngine {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        Write-Err "WSL no disponible."
        return 3
    }
    $letter = $DriveLetter.ToLower()
    $mnt = "/mnt/$letter"
    $argsJoined = ($AppArgs | ForEach-Object {
        if ($_ -match "[\s']") { "'" + ($_ -replace "'", "'\''") + "'" } else { $_ }
    }) -join " "

    Write-Info "=== Motor WSL (uv en Linux, ISOs en $mnt) ==="

    # -i login-ish + -t no disponible en wsl.exe antiguo; usar bash -lc desde sesion interactiva
    # wsl sin -e hereda TTY de la consola de Windows
    $cmd = @"
set -e
export VENTOY_ROOT=$mnt
export UV_LINK_MODE=copy
export PATH=`$HOME/.local/bin:`$PATH
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH=`$HOME/.local/bin:`$PATH
fi
mkdir -p `$HOME/projects
if [ ! -f `$HOME/projects/ventoy-iso-check/pyproject.toml ]; then
  git clone --depth 1 $GitUrl `$HOME/projects/ventoy-iso-check
else
  git -C `$HOME/projects/ventoy-iso-check pull --ff-only 2>/dev/null || true
fi
cd `$HOME/projects/ventoy-iso-check
uv sync
# Si no hay TTY, no uses menu
if [ -t 0 ] && [ -t 1 ]; then
  exec uv run ventoy-iso-check $argsJoined
else
  # fallback sin menu interactivo
  if echo '$argsJoined' | grep -q menu; then
    exec uv run ventoy-iso-check scan --sort age
  else
    exec uv run ventoy-iso-check $argsJoined
  fi
fi
"@

    $cmd = $cmd -replace "`r`n", "`n"
    # wsl invocado sin -e bash file: pasar por stdin no da TTY.
    # Mejor: wsl -e bash -lc "..." desde consola Windows (a menudo isatty true)
    & wsl --cd ~ -e bash -lc $cmd
    return $LASTEXITCODE
}

# =====================================================================
# Docker (ultimo recurso; USB extraible suele fallar)
# =====================================================================
function Invoke-DockerEngine {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Err "Docker no esta en PATH."
        return 3
    }
    docker info 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker Desktop no esta en marcha."
        return 3
    }
    if (-not $UsbRepo) {
        Write-Err "No hay repo USB para docker build."
        return 2
    }

    docker image inspect $Image 1>$null 2>$null
    $need = $Rebuild -or ($LASTEXITCODE -ne 0)
    if ($need) {
        Write-Info "docker build..."
        Push-Location $UsbRepo
        try {
            docker build -t $Image .
            if ($LASTEXITCODE -ne 0) { return $LASTEXITCODE }
        } finally { Pop-Location }
    }

    $letter = $DriveLetter
    $low = $DriveLetter.ToLower()
    foreach ($spec in @(
        @("--mount", "type=bind,source=${letter}:/,target=/ventoy"),
        @("-v", "${letter}:/:/ventoy"),
        @("-v", "//${low}/:/ventoy")
    )) {
        $probe = & docker run --rm --entrypoint /bin/sh @spec $Image -c 'find /ventoy -maxdepth 3 -name "*.iso" 2>/dev/null | wc -l' 2>&1
        $n = 0
        [void][int]::TryParse(("$probe").Trim(), [ref]$n)
        if ($n -ge 1) {
            Write-Info "Docker montaje OK ($n ISOs)"
            & docker run --rm -it -e VENTOY_ROOT=/ventoy @spec $Image @AppArgs
            return $LASTEXITCODE
        }
    }
    Write-Err "Docker no ve el USB. Usa -Engine Native (recomendado)."
    return 4
}

# =====================================================================
$code = 1
switch ($Engine) {
    "Native" { $code = Invoke-NativeEngine }
    "Wsl"    { $code = Invoke-WslEngine }
    "Docker" { $code = Invoke-DockerEngine }
    "Auto" {
        $code = Invoke-NativeEngine
        if ($code -ne 0) {
            Write-Warn "Native fallo; intentando WSL..."
            $code = Invoke-WslEngine
        }
    }
}

if ($code -ne 0) {
    Write-Warn "exit=$code"
    Write-Warn "Prueba manual (PowerShell):"
    Write-Warn "  winget install astral-sh.uv"
    Write-Warn "  `$env:VENTOY_ROOT = '$VentoyRoot'"
    Write-Warn "  cd `$env:USERPROFILE\projects\ventoy-iso-check"
    Write-Warn "  uv sync"
    Write-Warn "  uv run ventoy-iso-check menu"
}

exit $code
