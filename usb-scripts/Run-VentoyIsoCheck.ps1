#Requires -Version 5.1
<#
.SYNOPSIS
  Lanza ventoy-iso-check desde el disco Ventoy usando Docker.

.DESCRIPTION
  - Sin argumentos: menú interactivo.
  - Detecta la letra de unidad del USB automáticamente (E:, F:, D:, …).
  - Requiere Docker Desktop en marcha.
  - Monta la raíz del USB en /ventoy.

.EXAMPLE
  .\Run-VentoyIsoCheck.ps1
  .\Run-VentoyIsoCheck.ps1 scan
  .\Run-VentoyIsoCheck.ps1 check --only-outdated --urls
  .\Run-VentoyIsoCheck.ps1 -Rebuild
  .\Run-VentoyIsoCheck.ps1 -Drive F
#>
[CmdletBinding()]
param(
    [switch]$Menu,
    [switch]$Rebuild,
    [switch]$NoMenu,
    # Letra de unidad del Ventoy (sin ':'). Si se omite, se usa la del script.
    [string]$Drive = "",
    [string]$Image = "ventoy-iso-check:local",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$msg) { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Cyan }
function Write-Warn([string]$msg) { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Red }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Resolver repo (Dockerfile)
$RepoRoot = $null
if (Test-Path (Join-Path $ScriptDir "Dockerfile")) {
    $RepoRoot = $ScriptDir
} elseif (Test-Path (Join-Path (Split-Path $ScriptDir -Parent) "Dockerfile")) {
    $RepoRoot = (Resolve-Path (Split-Path $ScriptDir -Parent)).Path
} elseif (Test-Path (Join-Path $ScriptDir "ventoy-iso-check\Dockerfile")) {
    $RepoRoot = (Resolve-Path (Join-Path $ScriptDir "ventoy-iso-check")).Path
} else {
    Write-Err "No se encontro el repo (Dockerfile)."
    Write-Err "Esperado: <USB>\Scripts\ventoy-iso-check\"
    exit 2
}

# Letra de unidad: -Drive F  o  auto desde la ruta del script
if ($Drive) {
    $DriveLetter = $Drive.Trim().TrimEnd(':').TrimEnd('\').ToUpper()
} else {
    $DriveRoot = (Get-Item $RepoRoot).PSDrive.Root
    if (-not $DriveRoot) {
        $DriveRoot = [System.IO.Path]::GetPathRoot($RepoRoot)
    }
    $DriveLetter = $DriveRoot.TrimEnd('\').TrimEnd(':').ToUpper()
}

if (-not $DriveLetter -or $DriveLetter.Length -ne 1) {
    Write-Err "No se pudo detectar la letra de unidad. Usa: -Drive E"
    exit 2
}

$WindowsRoot = "${DriveLetter}:\"
if (-not (Test-Path $WindowsRoot)) {
    Write-Err "La unidad ${DriveLetter}: no existe o no esta montada."
    Write-Err "Conecta el USB y/o pasa -Drive <letra> (ej. -Drive F)"
    exit 2
}

Write-Info "Repo:   $RepoRoot"
Write-Info "Ventoy: $WindowsRoot  (cualquier letra; ahora ${DriveLetter}:)"
Write-Info "Image:  $Image"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker no esta instalado o no esta en el PATH."
    Write-Err "Instala Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 3
}

docker info 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker daemon no responde. Abre Docker Desktop y espera 'Engine running'."
    exit 3
}
Write-Info "Docker OK"

# Comprobar File sharing basico (listar carpeta en host)
$hostHints = @("Linux", "Bootloaders", "Scripts", "Herramientas", "Windows")
$seen = 0
foreach ($h in $hostHints) {
    if (Test-Path (Join-Path $WindowsRoot $h)) { $seen++ }
}
if ($seen -eq 0) {
    Write-Warn "En ${WindowsRoot} no se ven carpetas tipicas (Linux/Bootloaders/...). ¿Es este el USB Ventoy?"
} else {
    Write-Info "Host OK: se ven $seen carpetas tipicas en ${WindowsRoot}"
}

docker image inspect $Image 1>$null 2>$null
$imageExists = ($LASTEXITCODE -eq 0)
if ($Rebuild -or -not $imageExists) {
    Write-Info "Construyendo imagen (OBLIGATORIO si viste error sh\r)…"
    Push-Location $RepoRoot
    try {
        docker build --no-cache -t $Image .
        if ($LASTEXITCODE -ne 0) {
            Write-Err "docker build fallo (codigo $LASTEXITCODE)"
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Info "Imagen ya presente (usa -Rebuild si cambiaste el codigo o viste sh\r)"
}

# Argumentos
$wantMenu = $false
if ($Menu) {
    $wantMenu = $true
    $containerArgs = @("menu")
} elseif ($CliArgs -and $CliArgs.Count -gt 0) {
    $containerArgs = @($CliArgs)
    if ($CliArgs[0] -eq "menu") { $wantMenu = $true }
} elseif ($NoMenu) {
    $containerArgs = @("scan", "--sort", "age")
} else {
    $wantMenu = $true
    $containerArgs = @("menu")
}

# Montaje Docker Desktop Windows
# Documentado: -v E:\:/ventoy
# Alternativas: //e/:/ventoy
$volPrimary = "${DriveLetter}:\:/ventoy"
$volAlt = "//$($DriveLetter.ToLower())/:/ventoy"

function Test-Mount([string]$Vol) {
    # Entrypoint forzado a sh del sistema (no el del script) para el probe
    $probe = & docker run --rm --entrypoint /bin/sh `
        -v $Vol `
        $Image `
        -c "test -d /ventoy && ls -1 /ventoy 2>/dev/null | head -5 | wc -l" 2>&1
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    $line = ("$probe" -split "`n" | Where-Object { $_ -match '^\s*\d+\s*$' } | Select-Object -Last 1)
    $n = 0
    if ($line) { [void][int]::TryParse($line.Trim(), [ref]$n) }
    return ($n -ge 1)
}

Write-Info "Probando montaje: -v $volPrimary"
$vol = $null
if (Test-Mount $volPrimary) {
    $vol = $volPrimary
    Write-Info "Montaje OK: $volPrimary"
} else {
    Write-Info "Probando montaje: -v $volAlt"
    if (Test-Mount $volAlt) {
        $vol = $volAlt
        Write-Info "Montaje OK: $volAlt"
    }
}

if (-not $vol) {
    $vol = $volPrimary
    Write-Warn "No se valido el montaje; se usara: $vol"
    Write-Warn "Si total=0 ISOs:"
    Write-Warn "  Docker Desktop -> Settings -> Resources -> File sharing"
    Write-Warn "  Marca la unidad ${DriveLetter}:  (Apply & Restart)"
    Write-Warn "  Luego: .\Run-VentoyIsoCheck.ps1 -Rebuild"
}

Write-Info "docker run --rm -it -v $vol $Image $($containerArgs -join ' ')"

$dockerArgs = @(
    "run", "--rm", "-it",
    "-e", "VENTOY_ROOT=/ventoy",
    "-v", $vol,
    $Image
) + $containerArgs

& docker @dockerArgs
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Warn "docker exit=$code"
    if ($code -eq 127) {
        Write-Err "Error tipico de CRLF en entrypoint (sh\r). Solucion:"
        Write-Err "  .\Run-VentoyIsoCheck.ps1 -Rebuild"
        Write-Err "  (el Dockerfile ya corrige CRLF al construir)"
    }
    Write-Warn "Unidad distinta:  .\Run-VentoyIsoCheck.ps1 -Drive F"
    Write-Warn "Sin Docker / WSL:  uv run ventoy-iso-check menu /mnt/<letra>"
}

exit $code
