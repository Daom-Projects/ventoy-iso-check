# Actualiza o clona ventoy-iso-check en este USB (desde Windows nativo; mejor que WSL/9p).
# Requiere: git en PATH.
$ErrorActionPreference = "Stop"
$Dest = Join-Path $PSScriptRoot "ventoy-iso-check"
$Url = "https://github.com/Daom-Projects/ventoy-iso-check.git"
if (Test-Path (Join-Path $Dest ".git")) {
  Write-Host "git pull en $Dest"
  Push-Location $Dest
  git pull --ff-only
  Pop-Location
} elseif (Test-Path $Dest) {
  Write-Host "Carpeta sin .git — re-clonando limpio…"
  Remove-Item -Recurse -Force $Dest
  git clone $Url $Dest
} else {
  git clone $Url $Dest
}
Copy-Item (Join-Path $Dest "usb-scripts\Run-VentoyIsoCheck.ps1") (Join-Path $PSScriptRoot "Run-VentoyIsoCheck.ps1") -Force
Write-Host "Listo. Ejecuta: .\Run-VentoyIsoCheck.ps1"
