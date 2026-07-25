#Requires -Version 5.1
<#
.SYNOPSIS
  Lanza ventoy-iso-check desde el disco Ventoy usando Docker.

.DESCRIPTION
  Ubicación típica:
    E:\Scripts\ventoy-iso-check\usb-scripts\Run-VentoyIsoCheck.ps1

  - Exige Docker Desktop instalado y en ejecución (si no hay Docker, sale sin ejecutar).
  - Monta la raíz del volumen Ventoy en /ventoy.
  - Construye la imagen si no existe (o con -Rebuild).

.EXAMPLE
  .\Run-VentoyIsoCheck.ps1
  .\Run-VentoyIsoCheck.ps1 scan
  .\Run-VentoyIsoCheck.ps1 check --only-outdated --urls
  .\Run-VentoyIsoCheck.ps1 bootloaders
  .\Run-VentoyIsoCheck.ps1 ventoy
  .\Run-VentoyIsoCheck.ps1 -Menu
  .\Run-VentoyIsoCheck.ps1 -Rebuild check --urls
#>
[CmdletBinding()]
param(
    [switch]$Menu,
    [switch]$Rebuild,
    [string]$Image = "ventoy-iso-check:local",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$msg) { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Cyan }
function Write-Err([string]$msg)  { Write-Host "[ventoy-iso-check] $msg" -ForegroundColor Red }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Resolver repo (donde está el Dockerfile)
$RepoRoot = $null
if (Test-Path (Join-Path $ScriptDir "Dockerfile")) {
    $RepoRoot = $ScriptDir
} elseif (Test-Path (Join-Path (Split-Path $ScriptDir -Parent) "Dockerfile")) {
    $RepoRoot = (Resolve-Path (Split-Path $ScriptDir -Parent)).Path
} elseif (Test-Path (Join-Path $ScriptDir "ventoy-iso-check\Dockerfile")) {
    $RepoRoot = (Resolve-Path (Join-Path $ScriptDir "ventoy-iso-check")).Path
} else {
    Write-Err "No se encontró el repo (Dockerfile)."
    Write-Err "Clona en: <USB>\Scripts\ventoy-iso-check\"
    exit 2
}

# Raíz del USB = letra de unidad del repo (E:\)
$DriveRoot = (Get-Item $RepoRoot).PSDrive.Root
if (-not $DriveRoot) {
    $DriveRoot = [System.IO.Path]::GetPathRoot($RepoRoot)
}
$DriveLetter = $DriveRoot.TrimEnd('\').TrimEnd(':')

Write-Info "Repo:   $RepoRoot"
Write-Info "Ventoy: ${DriveLetter}:\"
Write-Info "Image:  $Image"

# Docker obligatorio
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker no está instalado o no está en el PATH."
    Write-Err "Instala Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Write-Err "Sin Docker este lanzador no ejecuta nada (por diseño)."
    exit 3
}

docker info 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker está instalado pero el daemon no responde."
    Write-Err "Abre Docker Desktop y espera a 'Engine running'."
    exit 3
}
Write-Info "Docker OK"

# Build si hace falta
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

if ($Menu) {
    $containerArgs = @("menu")
} elseif ($CliArgs -and $CliArgs.Count -gt 0) {
    $containerArgs = $CliArgs
} else {
    $containerArgs = @("scan", "--sort", "age")
}

# Docker Desktop: montar E: como /ventoy
# Forma portable: -v E:/ventoy
$vol = "${DriveLetter}:/ventoy"
Write-Info "docker run --rm -v $vol $Image $($containerArgs -join ' ')"

$dockerArgs = @("run", "--rm", "-e", "VENTOY_ROOT=/ventoy", "-v", $vol, $Image) + $containerArgs
# -it solo si hay consola interactiva
if ($Host.Name -eq "ConsoleHost") {
    $dockerArgs = @("run", "--rm", "-it", "-e", "VENTOY_ROOT=/ventoy", "-v", $vol, $Image) + $containerArgs
}

& docker @dockerArgs
exit $LASTEXITCODE
