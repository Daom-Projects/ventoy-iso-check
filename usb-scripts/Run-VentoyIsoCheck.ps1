#Requires -Version 5.1
<#
.SYNOPSIS
  Lanza ventoy-iso-check desde el disco Ventoy.

.DESCRIPTION
  Auto: intenta Docker; si el USB no se monta (total=0), usa WSL + uv.
  Sin argumentos: menu interactivo.

.EXAMPLE
  .\Run-VentoyIsoCheck.ps1
  .\Run-VentoyIsoCheck.ps1 -Engine Wsl
  .\Run-VentoyIsoCheck.ps1 -Engine Docker
  .\Run-VentoyIsoCheck.ps1 -Rebuild
  .\Run-VentoyIsoCheck.ps1 -Drive F
#>
[CmdletBinding()]
param(
    [switch]$Menu,
    [switch]$Rebuild,
    [switch]$NoMenu,
    [ValidateSet("Auto", "Docker", "Wsl")]
    [string]$Engine = "Auto",
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

# --- Repo (carpeta con Dockerfile) ---
$RepoRoot = $null
if (Test-Path (Join-Path $ScriptDir "Dockerfile")) {
    $RepoRoot = $ScriptDir
} elseif (Test-Path (Join-Path (Split-Path $ScriptDir -Parent) "Dockerfile")) {
    $RepoRoot = (Resolve-Path (Split-Path $ScriptDir -Parent)).Path
} elseif (Test-Path (Join-Path $ScriptDir "ventoy-iso-check\Dockerfile")) {
    $RepoRoot = (Resolve-Path (Join-Path $ScriptDir "ventoy-iso-check")).Path
} else {
    Write-Err "No se encontro el repo (Dockerfile). Esperado: <USB>\Scripts\ventoy-iso-check\"
    exit 2
}

# --- Letra de unidad del USB ---
if ($Drive) {
    $DriveLetter = $Drive.Trim().TrimEnd(':').TrimEnd('\').ToUpper()
} else {
    $DriveRoot = (Get-Item $RepoRoot).PSDrive.Root
    if (-not $DriveRoot) { $DriveRoot = [System.IO.Path]::GetPathRoot($RepoRoot) }
    $DriveLetter = $DriveRoot.TrimEnd('\').TrimEnd(':').ToUpper()
}
if (-not $DriveLetter -or $DriveLetter.Length -ne 1) {
    Write-Err "No se pudo detectar la letra de unidad. Usa: -Drive E"
    exit 2
}
$WindowsRoot = "${DriveLetter}:\"
if (-not (Test-Path $WindowsRoot)) {
    Write-Err "La unidad ${DriveLetter}: no existe. Usa -Drive F si el USB es otra letra."
    exit 2
}

Write-Info "Repo:   $RepoRoot"
Write-Info "Ventoy: $WindowsRoot"
Write-Info "Engine: $Engine"

# --- Argumentos del CLI ---
if ($Menu) {
    $containerArgs = @("menu")
} elseif ($CliArgs -and $CliArgs.Count -gt 0) {
    $containerArgs = @($CliArgs)
} elseif ($NoMenu) {
    $containerArgs = @("scan", "--sort", "age")
} else {
    $containerArgs = @("menu")
}
# Escapar para bash single-line: comillas simples en args se duplican
function ConvertTo-BashArgs([string[]]$Parts) {
    $out = @()
    foreach ($p in $Parts) {
        if ($p -match '[\s"$`]') {
            $esc = $p -replace "'", "'\''"
            $out += "'$esc'"
        } else {
            $out += $p
        }
    }
    return ($out -join " ")
}
$argsLine = ConvertTo-BashArgs $containerArgs
$argsLineDocker = $containerArgs  # array for docker

$hostIso = @(Get-ChildItem -Path (Join-Path $WindowsRoot "Linux") -Filter *.iso -ErrorAction SilentlyContinue).Count
$hostIso += @(Get-ChildItem -Path (Join-Path $WindowsRoot "Herramientas") -Filter *.iso -ErrorAction SilentlyContinue).Count
Write-Info "Host:   $hostIso ISO(s) en Linux/ + Herramientas/"

# =====================================================================
# WSL + uv  (no monta Docker; usa /mnt/<letra>)
# =====================================================================
function Invoke-WslEngine {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        Write-Err "WSL no esta instalado."
        return 3
    }

    $letter = $DriveLetter.ToLower()
    $mnt = "/mnt/$letter"

    Write-Info "WSL: comprobando $mnt ..."
    $check = & wsl -e bash -lc "ls $mnt/Linux/*.iso 2>/dev/null | wc -l"
    $n = 0
    [void][int]::TryParse(("$check").Trim(), [ref]$n)
    if ($n -lt 1) {
        Write-Err "WSL no ve ISOs en $mnt/Linux (cuento=$n)."
        Write-Err "Prueba: wsl -e ls $mnt/Linux"
        Write-Err "Si falla: wsl --shutdown  y vuelve a abrir la terminal."
        return 2
    }
    Write-Info "WSL: $n ISO(s) en $mnt/Linux"

    # Ruta del repo en WSL
    $repoWsl = $null
    if ($RepoRoot -match '^([A-Za-z]):\\') {
        $rl = $Matches[1].ToLower()
        $rest = $RepoRoot.Substring(2) -replace '\\', '/'
        $repoWsl = "/mnt/$rl/$rest"
    } else {
        $repoWsl = "$mnt/Scripts/ventoy-iso-check"
    }

    # Cadena bash SOLO con comillas simples de PowerShell (no se interpreta for/if)
    # Placeholders: __MNT__ __REPO__ __ARGS__
    $bashTemplate = 'set -e
export VENTOY_ROOT="__MNT__"
REPO="__REPO__"
if [ ! -f "$REPO/pyproject.toml" ]; then
  for c in "__MNT__/Scripts/ventoy-iso-check" "$HOME/projects/ventoy-iso-check"; do
    if [ -f "$c/pyproject.toml" ]; then REPO="$c"; break; fi
  done
fi
if [ ! -f "$REPO/pyproject.toml" ]; then
  echo "[ventoy-iso-check] No pyproject.toml en $REPO" >&2
  exit 2
fi
echo "[ventoy-iso-check] WSL repo=$REPO VENTOY_ROOT=$VENTOY_ROOT"
cd "$REPO"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "[ventoy-iso-check] Instalando uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv sync
exec uv run ventoy-iso-check __ARGS__
'

    $bash = $bashTemplate.Replace('__MNT__', $mnt).Replace('__REPO__', $repoWsl).Replace('__ARGS__', $argsLine)

    # Escribir script temporal en el USB (WSL lo ve en /mnt/e/...) para evitar problemas de comillas
    $tmpWin = Join-Path $WindowsRoot "Scripts\_vic_run.sh"
    $tmpWsl = "$mnt/Scripts/_vic_run.sh"
    # LF only
    $bashLf = $bash -replace "`r`n", "`n" -replace "`r", "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmpWin, $bashLf, $utf8NoBom)

    Write-Info "WSL+uv: bash $tmpWsl"
    & wsl -e bash $tmpWsl
    $code = $LASTEXITCODE
    Remove-Item -Force $tmpWin -ErrorAction SilentlyContinue
    return $code
}

# =====================================================================
# Docker
# =====================================================================
function Ensure-DockerImage {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Err "Docker no esta en el PATH."
        return $false
    }
    docker info 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker daemon no responde. Abre Docker Desktop."
        return $false
    }

    docker image inspect $Image 1>$null 2>$null
    $exists = ($LASTEXITCODE -eq 0)
    $need = $Rebuild -or (-not $exists)

    if ($exists -and -not $need) {
        $probeOut = & docker run --rm $Image -V 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0 -or $probeOut -match 'sh\\r') {
            Write-Warn "Imagen rota; reconstruyendo..."
            $need = $true
        } else {
            Write-Info "Imagen OK: $($probeOut.Trim())"
        }
    }

    if ($need) {
        Write-Info "docker build (puede tardar)..."
        Push-Location $RepoRoot
        try {
            docker build --no-cache -t $Image .
            if ($LASTEXITCODE -ne 0) { return $false }
        } finally {
            Pop-Location
        }
        $v = & docker run --rm $Image -V 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Build listo pero -V falla: $v"
            return $false
        }
        Write-Info "Build OK: $($v.Trim())"
    }
    return $true
}

function Test-DockerMount {
    param([string[]]$VolArgs)
    $cmd = 'echo ISOS:$(find /ventoy -maxdepth 3 -type f \( -iname "*.iso" -o -iname "*.img" \) 2>/dev/null | wc -l); echo ENTRIES:$(ls -1 /ventoy 2>/dev/null | wc -l); ls -1 /ventoy 2>/dev/null | head -6'
    $out = & docker run --rm --entrypoint /bin/sh @VolArgs $Image -c $cmd 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        return @{ Ok = $false; Isos = 0; Detail = $out }
    }
    $isos = 0
    if ($out -match 'ISOS:(\d+)') { $isos = [int]$Matches[1] }
    return @{ Ok = ($isos -ge 1); Isos = $isos; Detail = $out.Trim() }
}

function Invoke-DockerEngine {
    if (-not (Ensure-DockerImage)) { return 3 }

    $letter = $DriveLetter
    $low = $DriveLetter.ToLower()

    $candidates = @(
        @{ Label = "mount E:/";   Args = @("--mount", "type=bind,source=${letter}:/,target=/ventoy") },
        @{ Label = "mount E:\";   Args = @("--mount", "type=bind,source=${letter}:\,target=/ventoy") },
        @{ Label = "-v E:/:/";    Args = @("-v", "${letter}:/:/ventoy") },
        @{ Label = "-v E:\:/";    Args = @("-v", "${letter}:\:/ventoy") },
        @{ Label = "-v //e/";     Args = @("-v", "//${low}/:/ventoy") }
    )

    $chosen = $null
    foreach ($c in $candidates) {
        Write-Info "Probando Docker: $($c.Label)"
        $r = Test-DockerMount -VolArgs $c.Args
        if ($r.Ok) {
            Write-Info "Montaje OK ($($r.Isos) ISO(s))"
            $chosen = $c
            break
        }
        Write-Warn "  vacio o error (isos=$($r.Isos))"
    }

    if (-not $chosen) {
        Write-Err "Docker no ve ISOs en el USB (montaje vacio). Tipico con unidades extraibles."
        return 4
    }

    Write-Info "docker run -it $($chosen.Label) $Image $($argsLineDocker -join ' ')"
    $dockerArgs = @("run", "--rm", "-it", "-e", "VENTOY_ROOT=/ventoy") + $chosen.Args + @($Image) + $argsLineDocker
    & docker @dockerArgs
    return $LASTEXITCODE
}

# =====================================================================
# Seleccion
# =====================================================================
$code = 1
switch ($Engine) {
    "Docker" {
        $code = Invoke-DockerEngine
        if ($code -eq 4) {
            Write-Warn "Fallback a WSL+uv..."
            $code = Invoke-WslEngine
        }
    }
    "Wsl" {
        $code = Invoke-WslEngine
    }
    default {
        $dockerReady = $false
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            docker info 1>$null 2>$null
            $dockerReady = ($LASTEXITCODE -eq 0)
        }
        if ($dockerReady) {
            $code = Invoke-DockerEngine
            if ($code -eq 4) {
                Write-Warn "Docker no monta el USB. Usando WSL+uv..."
                $code = Invoke-WslEngine
            }
        } else {
            Write-Warn "Docker no disponible. Usando WSL+uv..."
            $code = Invoke-WslEngine
        }
    }
}

if ($code -ne 0) {
    Write-Warn "exit=$code"
    Write-Warn "Manual WSL:"
    $L = $DriveLetter.ToLower()
    Write-Warn "  wsl -e bash -lc `"export VENTOY_ROOT=/mnt/$L; cd /mnt/$L/Scripts/ventoy-iso-check && uv run ventoy-iso-check menu`""
}

exit $code
