#Requires -Version 5.1
<#
.SYNOPSIS
  Lanza ventoy-iso-check desde el disco Ventoy.

.DESCRIPTION
  1) Intenta Docker montando la unidad del USB en /ventoy.
  2) Si el montaje queda vacio (caso tipico con USB + Docker Desktop),
     usa WSL + uv con /mnt/<letra> (sin montar volumen en Docker).

  Sin argumentos: menu interactivo.

.EXAMPLE
  .\Run-VentoyIsoCheck.ps1
  .\Run-VentoyIsoCheck.ps1 -Engine Docker
  .\Run-VentoyIsoCheck.ps1 -Engine Wsl
  .\Run-VentoyIsoCheck.ps1 -Drive F scan
  .\Run-VentoyIsoCheck.ps1 -Rebuild
#>
[CmdletBinding()]
param(
    [switch]$Menu,
    [switch]$Rebuild,
    [switch]$NoMenu,
    # Auto | Docker | Wsl
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

# --- Repo ---
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

# --- Letra de unidad ---
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
    Write-Err "La unidad ${DriveLetter}: no existe. Conecta el USB o usa -Drive F"
    exit 2
}

Write-Info "Repo:   $RepoRoot"
Write-Info "Ventoy: $WindowsRoot"
Write-Info "Engine: $Engine"

# --- Args CLI ---
if ($Menu) {
    $containerArgs = @("menu")
} elseif ($CliArgs -and $CliArgs.Count -gt 0) {
    $containerArgs = @($CliArgs)
} elseif ($NoMenu) {
    $containerArgs = @("scan", "--sort", "age")
} else {
    $containerArgs = @("menu")
}
$argsLine = ($containerArgs -join " ")

# Host tiene ISOs?
$hostIso = @(Get-ChildItem -Path (Join-Path $WindowsRoot "Linux") -Filter *.iso -ErrorAction SilentlyContinue).Count
$hostIso += @(Get-ChildItem -Path (Join-Path $WindowsRoot "Herramientas") -Filter *.iso -ErrorAction SilentlyContinue).Count
Write-Info "Host:   $hostIso ISO(s) vistas en Linux/ + Herramientas/"

# =====================================================================
# Motor WSL + uv (fiable con USB; no depende de File sharing de Docker)
# =====================================================================
function Invoke-WslEngine {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        Write-Err "WSL no esta instalado."
        return 3
    }
    $letter = $DriveLetter.ToLower()
    $mnt = "/mnt/$letter"
    Write-Info "WSL: comprobando $mnt …"

    $check = & wsl -e bash -lc "test -d '$mnt/Linux' && ls '$mnt'/Linux/*.iso 2>/dev/null | wc -l" 2>&1
    $n = 0
    [void][int]::TryParse(("$check").Trim(), [ref]$n)
    if ($n -lt 1) {
        Write-Err "WSL no ve ISOs en $mnt/Linux"
        Write-Err "En WSL: ls $mnt/Linux"
        Write-Err "Si falla, monta la unidad o reinicia WSL: wsl --shutdown"
        return 2
    }
    Write-Info "WSL: $n ISO(s) en $mnt/Linux — OK"

    # Repo en USB o en home de WSL
    $repoWslCandidates = @(
        "$mnt/Scripts/ventoy-iso-check",
        "/mnt/$letter/Scripts/ventoy-iso-check"
    )
    # Convertir ruta Windows del repo a /mnt/x/...
    if ($RepoRoot -match '^[A-Za-z]:\\') {
        $rl = $RepoRoot.Substring(0, 1).ToLower()
        $rp = ($RepoRoot.Substring(2) -replace '\\', '/')
        $repoWslCandidates = @("/mnt/$rl/$rp") + $repoWslCandidates
    }
    $repoWslCandidates += @(
        "$HOME/projects/ventoy-iso-check",
        "~/projects/ventoy-iso-check"
    )

    $bashArgs = $argsLine -replace '"', '\"'
    $script = @"
set -e
export VENTOY_ROOT='$mnt'
REPO=''
for c in $($repoWslCandidates | ForEach-Object { "'$_'" }) ; do
  # expand ~
  c=`${c/#\~/$HOME}
  if [ -f "`$c/pyproject.toml" ]; then REPO=`$c; break; fi
done
if [ -z "`$REPO" ]; then
  echo '[ventoy-iso-check] No se encontro el repo en WSL (pyproject.toml).' >&2
  echo '  Clona o copia en: $mnt/Scripts/ventoy-iso-check' >&2
  echo '  o: ~/projects/ventoy-iso-check' >&2
  exit 2
fi
echo "[ventoy-iso-check] WSL repo: `$REPO"
echo "[ventoy-iso-check] VENTOY_ROOT=`$VENTOY_ROOT"
cd "`$REPO"
if ! command -v uv >/dev/null 2>&1; then
  echo '[ventoy-iso-check] uv no esta en WSL. Instalando…' >&2
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="`$HOME/.local/bin:`$PATH"
fi
export PATH="`$HOME/.local/bin:`$PATH"
uv sync --quiet 2>/dev/null || uv sync
exec uv run ventoy-iso-check $bashArgs
"@

    Write-Info "Lanzando via WSL + uv (VENTOY_ROOT=$mnt)…"
    # -e no inicia login shell; PATH de uv se exporta en el script
    & wsl -e bash -lc $script
    return $LASTEXITCODE
}

# =====================================================================
# Motor Docker
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
        if ($LASTEXITCODE -ne 0 -or $probeOut -match 'sh\\r' -or $probeOut -match "sh`r") {
            Write-Warn "Imagen rota; reconstruyendo…"
            $need = $true
        } else {
            Write-Info "Imagen OK: $($probeOut.Trim())"
        }
    }

    if ($need) {
        Write-Info "docker build (puede tardar)…"
        Push-Location $RepoRoot
        try {
            docker build --no-cache -t $Image .
            if ($LASTEXITCODE -ne 0) { return $false }
        } finally { Pop-Location }
        $v = & docker run --rm $Image -V 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Build OK pero -V falla: $v"
            return $false
        }
        Write-Info "Build OK: $($v.Trim())"
    }
    return $true
}

function Test-DockerMount {
    param([string[]]$DockerVolArgs)
    # Cuenta entradas en /ventoy y si hay .iso en subdirs de primer nivel
    $cmd = 'echo ENTRIES:$(ls -1 /ventoy 2>/dev/null | wc -l); echo ISOS:$(find /ventoy -maxdepth 3 -type f \( -iname "*.iso" -o -iname "*.img" \) 2>/dev/null | wc -l); ls -1 /ventoy 2>/dev/null | head -8'
    $out = & docker run --rm --entrypoint /bin/sh @DockerVolArgs $Image -c $cmd 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        return @{ Ok = $false; Detail = $out; Isos = 0; Entries = 0 }
    }
    $entries = 0; $isos = 0
    if ($out -match 'ENTRIES:(\d+)') { $entries = [int]$Matches[1] }
    if ($out -match 'ISOS:(\d+)') { $isos = [int]$Matches[1] }
    return @{
        Ok = ($isos -ge 1 -or $entries -ge 3)
        Detail = $out.Trim()
        Isos = $isos
        Entries = $entries
    }
}

function Invoke-DockerEngine {
    if (-not (Ensure-DockerImage)) { return 3 }

    $letter = $DriveLetter
    $low = $DriveLetter.ToLower()

    # Candidatos de montaje (orden: los que suelen funcionar en Docker Desktop)
    $candidates = @(
        @{ Label = "--mount bind E:/";  Args = @("--mount", "type=bind,source=${letter}:/,target=/ventoy") },
        @{ Label = "--mount bind E:\";  Args = @("--mount", "type=bind,source=${letter}:\,target=/ventoy") },
        @{ Label = "-v E:/:/ventoy";    Args = @("-v", "${letter}:/:/ventoy") },
        @{ Label = "-v E:\:/ventoy";    Args = @("-v", "${letter}:\:/ventoy") },
        @{ Label = "-v //e/:/ventoy";   Args = @("-v", "//${low}/:/ventoy") }
    )

    $chosen = $null
    foreach ($c in $candidates) {
        Write-Info "Probando montaje Docker: $($c.Label)"
        $r = Test-DockerMount -DockerVolArgs $c.Args
        if ($r.Ok) {
            Write-Info "Montaje OK ($($r.Isos) ISO(s), $($r.Entries) entradas en /ventoy)"
            Write-Info $r.Detail
            $chosen = $c
            break
        } else {
            Write-Warn "  no sirve (isos=$($r.Isos) entries=$($r.Entries))"
            if ($r.Detail -and $r.Detail.Length -lt 400) {
                Write-Warn "  $($r.Detail -replace "`r?`n", ' | ')"
            }
        }
    }

    if (-not $chosen) {
        Write-Err "Docker no puede ver las ISOs del USB (montaje vacio)."
        Write-Err "Causas tipicas:"
        Write-Err "  1) Docker Desktop -> Settings -> Resources -> File sharing -> marca ${letter}:"
        Write-Err "  2) Unidades extraibles a veces no se comparten bien con el backend WSL2"
        Write-Err "Solucion recomendada: usar WSL+uv (este script lo hace en -Engine Auto)"
        return 4
    }

    Write-Info "docker run --rm -it $($chosen.Label) $Image $argsLine"
    $dockerArgs = @("run", "--rm", "-it", "-e", "VENTOY_ROOT=/ventoy") + $chosen.Args + @($Image) + $containerArgs
    & docker @dockerArgs
    return $LASTEXITCODE
}

# =====================================================================
# Seleccion de motor
# =====================================================================
$code = 1
switch ($Engine) {
    "Docker" {
        $code = Invoke-DockerEngine
        if ($code -eq 4) {
            Write-Warn "Fallback automatico a WSL+uv…"
            $code = Invoke-WslEngine
        }
    }
    "Wsl" {
        $code = Invoke-WslEngine
    }
    default {
        # Auto: si Docker monta bien, Docker; si no, WSL+uv
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            docker info 1>$null 2>$null
            if ($LASTEXITCODE -eq 0) {
                $code = Invoke-DockerEngine
                if ($code -eq 4) {
                    Write-Warn "Docker no monta el USB. Cambiando a WSL + uv…"
                    $code = Invoke-WslEngine
                }
            } else {
                Write-Warn "Docker no responde; usando WSL + uv…"
                $code = Invoke-WslEngine
            }
        } else {
            Write-Warn "Sin Docker; usando WSL + uv…"
            $code = Invoke-WslEngine
        }
    }
}

if ($code -ne 0) {
    Write-Warn "exit=$code"
    Write-Warn "Prueba manual WSL:"
    Write-Warn "  wsl -e bash -lc `"export VENTOY_ROOT=/mnt/$($DriveLetter.ToLower()); cd /mnt/$($DriveLetter.ToLower())/Scripts/ventoy-iso-check && uv run ventoy-iso-check menu`""
}
exit $code
