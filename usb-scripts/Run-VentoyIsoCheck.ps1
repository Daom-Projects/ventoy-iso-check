#Requires -Version 5.1
<#
.SYNOPSIS
  Lanza ventoy-iso-check desde el disco Ventoy.

.DESCRIPTION
  Auto: intenta Docker; si el USB no se monta, usa WSL + uv.
  En WSL el codigo corre desde ~/projects/ventoy-iso-check (ext4),
  NO desde E:\ (el .venv en USB/9p falla con Operation not permitted).
  Solo se usa /mnt/<letra> como VENTOY_ROOT (lectura de ISOs).

.EXAMPLE
  .\Run-VentoyIsoCheck.ps1
  .\Run-VentoyIsoCheck.ps1 -Engine Wsl
  .\Run-VentoyIsoCheck.ps1 -Engine Docker -Rebuild
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

# --- Repo en USB (solo para Docker build / localizar unidad) ---
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
    Write-Err "La unidad ${DriveLetter}: no existe."
    exit 2
}

Write-Info "Repo USB: $RepoRoot"
Write-Info "Ventoy:   $WindowsRoot"
Write-Info "Engine:   $Engine"

if ($Menu) {
    $containerArgs = @("menu")
} elseif ($CliArgs -and $CliArgs.Count -gt 0) {
    $containerArgs = @($CliArgs)
} elseif ($NoMenu) {
    $containerArgs = @("scan", "--sort", "age")
} else {
    $containerArgs = @("menu")
}

function ConvertTo-BashArgs([string[]]$Parts) {
    $out = @()
    foreach ($p in $Parts) {
        if ($p -match "[\s'`"`$]") {
            $esc = $p -replace "'", "'\''"
            $out += "'$esc'"
        } else {
            $out += $p
        }
    }
    return ($out -join " ")
}
$argsLine = ConvertTo-BashArgs $containerArgs

$hostIso = @(Get-ChildItem -Path (Join-Path $WindowsRoot "Linux") -Filter *.iso -ErrorAction SilentlyContinue).Count
$hostIso += @(Get-ChildItem -Path (Join-Path $WindowsRoot "Herramientas") -Filter *.iso -ErrorAction SilentlyContinue).Count
Write-Info "Host:     $hostIso ISO(s) en Linux/ + Herramientas/"

# =====================================================================
# WSL + uv: codigo en ~/projects (Linux FS), ISOs en /mnt/<letra>
# =====================================================================
function Invoke-WslEngine {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        Write-Err "WSL no esta instalado."
        return 3
    }

    $letter = $DriveLetter.ToLower()
    $mnt = "/mnt/$letter"
    $wslRepo = '$HOME/projects/ventoy-iso-check'
    $gitUrl = "https://github.com/Daom-Projects/ventoy-iso-check.git"

    Write-Info "WSL: comprobando $mnt ..."
    $check = & wsl -e bash -lc "ls $mnt/Linux/*.iso 2>/dev/null | wc -l"
    $n = 0
    [void][int]::TryParse(("$check").Trim(), [ref]$n)
    if ($n -lt 1) {
        Write-Err "WSL no ve ISOs en $mnt/Linux."
        Write-Err "Prueba: wsl -e ls $mnt/Linux"
        Write-Err "Si falla: wsl --shutdown"
        return 2
    }
    Write-Info "WSL: $n ISO(s) en $mnt/Linux"

    # Script bash escrito a archivo temporal en %TEMP% (disco Windows del sistema,
    # no en el USB) y ejecutado via /mnt/c/...
    $bash = @"
set -e
export VENTOY_ROOT='$mnt'
export UV_LINK_MODE=copy
export PATH="`$HOME/.local/bin:`$PATH"

# 1) uv
if ! command -v uv >/dev/null 2>&1; then
  echo '[ventoy-iso-check] Instalando uv en WSL...'
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="`$HOME/.local/bin:`$PATH"
fi

# 2) Repo en HOME (ext4) — NUNCA .venv en el USB/9p
REPO="`$HOME/projects/ventoy-iso-check"
mkdir -p "`$HOME/projects"
if [ ! -f "`$REPO/pyproject.toml" ]; then
  echo "[ventoy-iso-check] Clonando $gitUrl -> `$REPO"
  git clone --depth 1 "$gitUrl" "`$REPO"
else
  echo "[ventoy-iso-check] Repo WSL: `$REPO"
  # actualizar si es un clon limpio (no fallar si hay cambios locales)
  git -C "`$REPO" pull --ff-only 2>/dev/null || true
fi

cd "`$REPO"
# venv siempre bajo el proyecto en HOME (no en /mnt/e)
echo "[ventoy-iso-check] VENTOY_ROOT=`$VENTOY_ROOT"
echo "[ventoy-iso-check] uv sync en `$REPO (filesystem Linux)"
uv sync
exec uv run ventoy-iso-check $argsLine
"@

    # Expand only what we need: $mnt $gitUrl $argsLine already in string via @"
    # Escape: we used `$ for bash vars. Good.
    # But @" also expanded $argsLine - good. $gitUrl - good. $mnt - good.

    $bashLf = ($bash -replace "`r`n", "`n") -replace "`r", "`n"
    $tmpWin = Join-Path $env:TEMP "vic-run-$PID.sh"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmpWin, $bashLf, $utf8)

    # Windows path -> /mnt/c/Users/...
    $tmpFull = (Resolve-Path $tmpWin).Path
    if ($tmpFull -match '^([A-Za-z]):\\') {
        $dl = $Matches[1].ToLower()
        $rest = $tmpFull.Substring(2) -replace '\\', '/'
        $tmpWsl = "/mnt/$dl/$rest"
    } else {
        Write-Err "No se pudo convertir ruta temp a WSL: $tmpFull"
        return 2
    }

    Write-Info "WSL+uv: repo=~/projects/ventoy-iso-check  VENTOY_ROOT=$mnt"
    Write-Info "script: $tmpWsl"
    & wsl -e bash "$tmpWsl"
    $code = $LASTEXITCODE
    Remove-Item -Force $tmpWin -ErrorAction SilentlyContinue
    return $code
}

# =====================================================================
# Docker (suele fallar con USB extraible)
# =====================================================================
function Ensure-DockerImage {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    docker info 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) { return $false }

    docker image inspect $Image 1>$null 2>$null
    $exists = ($LASTEXITCODE -eq 0)
    $need = $Rebuild -or (-not $exists)

    if ($exists -and -not $need) {
        $probeOut = & docker run --rm $Image -V 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0 -or $probeOut -match 'sh\\r') { $need = $true }
        else { Write-Info "Imagen OK: $($probeOut.Trim())" }
    }

    if ($need) {
        Write-Info "docker build..."
        Push-Location $RepoRoot
        try {
            docker build --no-cache -t $Image .
            if ($LASTEXITCODE -ne 0) { return $false }
        } finally { Pop-Location }
        $v = & docker run --rm $Image -V 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { return $false }
        Write-Info "Build OK: $($v.Trim())"
    }
    return $true
}

function Test-DockerMount([string[]]$VolArgs) {
    $cmd = 'echo ISOS:$(find /ventoy -maxdepth 3 -type f \( -iname "*.iso" -o -iname "*.img" \) 2>/dev/null | wc -l)'
    $out = & docker run --rm --entrypoint /bin/sh @VolArgs $Image -c $cmd 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { return @{ Ok = $false; Isos = 0 } }
    $isos = 0
    if ($out -match 'ISOS:(\d+)') { $isos = [int]$Matches[1] }
    return @{ Ok = ($isos -ge 1); Isos = $isos }
}

function Invoke-DockerEngine {
    if (-not (Ensure-DockerImage)) {
        Write-Err "Docker no disponible o build fallo."
        return 3
    }

    $letter = $DriveLetter
    $low = $DriveLetter.ToLower()
    $candidates = @(
        @{ Label = "mount E:/"; Args = @("--mount", "type=bind,source=${letter}:/,target=/ventoy") },
        @{ Label = "-v E:/:/";  Args = @("-v", "${letter}:/:/ventoy") },
        @{ Label = "-v //e/";   Args = @("-v", "//${low}/:/ventoy") }
    )

    $chosen = $null
    foreach ($c in $candidates) {
        Write-Info "Probando Docker: $($c.Label)"
        $r = Test-DockerMount $c.Args
        if ($r.Ok) {
            Write-Info "Montaje OK ($($r.Isos) ISO(s))"
            $chosen = $c
            break
        }
        Write-Warn "  vacio (isos=$($r.Isos))"
    }

    if (-not $chosen) {
        Write-Err "Docker no ve ISOs del USB (tipico con unidades extraibles)."
        return 4
    }

    $dockerArgs = @("run", "--rm", "-it", "-e", "VENTOY_ROOT=/ventoy") + $chosen.Args + @($Image) + $containerArgs
    & docker @dockerArgs
    return $LASTEXITCODE
}

# =====================================================================
$code = 1
switch ($Engine) {
    "Docker" {
        $code = Invoke-DockerEngine
        if ($code -eq 4) {
            Write-Warn "Fallback WSL+uv..."
            $code = Invoke-WslEngine
        }
    }
    "Wsl" { $code = Invoke-WslEngine }
    default {
        $dockerReady = $false
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            docker info 1>$null 2>$null
            $dockerReady = ($LASTEXITCODE -eq 0)
        }
        # Con USB, preferir WSL primero (Docker casi nunca monta extraibles)
        if ($hostIso -gt 0) {
            Write-Info "USB detectado: priorizando WSL+uv (Docker suele fallar con extraibles)"
            $code = Invoke-WslEngine
            if ($code -ne 0 -and $dockerReady) {
                Write-Warn "WSL fallo; intentando Docker..."
                $code = Invoke-DockerEngine
            }
        } elseif ($dockerReady) {
            $code = Invoke-DockerEngine
            if ($code -eq 4) { $code = Invoke-WslEngine }
        } else {
            $code = Invoke-WslEngine
        }
    }
}

if ($code -ne 0) {
    Write-Warn "exit=$code"
    $L = $DriveLetter.ToLower()
    Write-Warn "Manual:"
    Write-Warn "  wsl"
    Write-Warn "  export VENTOY_ROOT=/mnt/$L"
    Write-Warn "  cd ~/projects/ventoy-iso-check   # o: git clone https://github.com/Daom-Projects/ventoy-iso-check.git ~/projects/ventoy-iso-check"
    Write-Warn "  uv sync && uv run ventoy-iso-check menu"
}

exit $code
