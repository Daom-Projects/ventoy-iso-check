#Requires -Version 5.1
<#
.SYNOPSIS
  Lanza ventoy-iso-check desde el disco Ventoy usando Docker.

.DESCRIPTION
  Sin argumentos abre el **menú interactivo**.
  Requiere Docker Desktop en marcha.
  Monta la raíz del USB (letra de esta carpeta) en /ventoy.

.EXAMPLE
  .\Run-VentoyIsoCheck.ps1
  .\Run-VentoyIsoCheck.ps1 scan
  .\Run-VentoyIsoCheck.ps1 check --only-outdated --urls
  .\Run-VentoyIsoCheck.ps1 bootloaders
  .\Run-VentoyIsoCheck.ps1 -Rebuild
#>
[CmdletBinding()]
param(
    [switch]$Menu,
    [switch]$Rebuild,
    [switch]$NoMenu,
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
    Write-Err "No se encontró el repo (Dockerfile)."
    Write-Err "Esperado: <USB>\Scripts\ventoy-iso-check\"
    exit 2
}

$DriveRoot = (Get-Item $RepoRoot).PSDrive.Root
if (-not $DriveRoot) {
    $DriveRoot = [System.IO.Path]::GetPathRoot($RepoRoot)
}
$DriveLetter = $DriveRoot.TrimEnd('\').TrimEnd(':')

Write-Info "Repo:   $RepoRoot"
Write-Info "Ventoy: ${DriveLetter}:\"
Write-Info "Image:  $Image"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker no está instalado o no está en el PATH."
    Write-Err "Instala Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 3
}

docker info 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker daemon no responde. Abre Docker Desktop y espera 'Engine running'."
    exit 3
}
Write-Info "Docker OK"

docker image inspect $Image 1>$null 2>$null
$imageExists = ($LASTEXITCODE -eq 0)
if ($Rebuild -or -not $imageExists) {
    Write-Info "Construyendo imagen (puede tardar la primera vez)…"
    Push-Location $RepoRoot
    try {
        docker build -t $Image .
        if ($LASTEXITCODE -ne 0) {
            Write-Err "docker build falló (código $LASTEXITCODE)"
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Info "Imagen ya presente (usa -Rebuild para reconstruir)"
}

# --- Argumentos del contenedor ---
# Default: menú interactivo (no scan silencioso)
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

# --- Montaje Docker Desktop en Windows ---
# Formas que suelen funcionar (en orden de preferencia):
#   E:\:/ventoy   (documentado por Docker Desktop)
#   //e/:/ventoy
#   E:/ventoy     (a veces monta vacío — NO preferir)
$volCandidates = @(
    ("{0}:\:/ventoy" -f $DriveLetter),
    ("//{0}/:/ventoy" -f $DriveLetter.ToLower()),
    ("{0}:/ventoy" -f $DriveLetter)
)

function Test-VentoyMount([string]$VolSpec) {
    # ¿Se ven carpetas del USB dentro de /ventoy?
    $probe = & docker run --rm --entrypoint /bin/sh `
        -v $VolSpec $Image `
        -c "ls -1 /ventoy 2>/dev/null | wc -l" 2>$null
    if ($LASTEXITCODE -ne 0) { return $false }
    $n = 0
    [void][int]::TryParse(("${probe}".Trim()), [ref]$n)
    return ($n -ge 1)
}

$vol = $null
foreach ($cand in $volCandidates) {
    Write-Info "Probando montaje: -v $cand"
    if (Test-VentoyMount $cand) {
        $vol = $cand
        Write-Info "Montaje OK: $cand"
        break
    }
}

if (-not $vol) {
    # Último intento: forma clásica aunque el probe falle (algunos shells)
    $vol = ("{0}:\:/ventoy" -f $DriveLetter)
    Write-Warn "No se pudo validar el montaje; usando $vol"
    Write-Warn "Si sale total=0 ISOs, en Docker Desktop: Settings → Resources → File sharing y comparte la unidad ${DriveLetter}:"
}

Write-Info "Comando: docker run --rm -it -v $vol $Image $($containerArgs -join ' ')"

# -it siempre en menú (y en general para PowerShell interactivo)
$base = @(
    "run", "--rm",
    "-e", "VENTOY_ROOT=/ventoy",
    "-v", $vol,
    $Image
) + $containerArgs

if ($wantMenu -or [Environment]::UserInteractive) {
    $base = @(
        "run", "--rm", "-it",
        "-e", "VENTOY_ROOT=/ventoy",
        "-v", $vol,
        $Image
    ) + $containerArgs
}

& docker @base
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Warn "docker exit=$code"
    Write-Warn "Si el menú no aparece o no hay ISOs:"
    Write-Warn "  1) Docker Desktop → Settings → Resources → File sharing → unidad ${DriveLetter}:"
    Write-Warn "  2) Prueba: docker run --rm -it -v ${DriveLetter}:\:/ventoy $Image scan"
    Write-Warn "  3) O con WSL+uv:  uv run ventoy-iso-check menu /mnt/e"
}
exit $code
