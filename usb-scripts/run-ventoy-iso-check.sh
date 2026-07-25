#!/usr/bin/env bash
# Lanzador portable (Linux / WSL / macOS) — requiere Docker.
# Uso:
#   ./run-ventoy-iso-check.sh
#   ./run-ventoy-iso-check.sh check --only-outdated --urls
#   ./run-ventoy-iso-check.sh bootloaders
#   MENU=1 ./run-ventoy-iso-check.sh
set -euo pipefail

info() { printf '\033[0;36m[ventoy-iso-check]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[ventoy-iso-check]\033[0m %s\n' "$*"; }
err()  { printf '\033[0;31m[ventoy-iso-check]\033[0m %s\n' "$*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolver repo (Dockerfile)
if [[ -f "$SCRIPT_DIR/Dockerfile" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../Dockerfile" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -f "$SCRIPT_DIR/ventoy-iso-check/Dockerfile" ]]; then
  REPO_ROOT="$SCRIPT_DIR/ventoy-iso-check"
else
  err "No se encontró Dockerfile. Clona el repo en Scripts/ventoy-iso-check"
  exit 2
fi

# Raíz Ventoy: preferir $VENTOY_ROOT, luego /ventoy, luego padre de Scripts, luego /mnt/e
if [[ -n "${VENTOY_ROOT:-}" && -d "$VENTOY_ROOT" ]]; then
  VROOT="$VENTOY_ROOT"
elif [[ -d /ventoy ]]; then
  VROOT=/ventoy
else
  # .../Scripts/ventoy-iso-check → USB root si existe Bootloaders/ o Linux/
  CAND="$(cd "$REPO_ROOT/../.." 2>/dev/null && pwd || true)"
  if [[ -n "$CAND" && ( -d "$CAND/Bootloaders" || -d "$CAND/Linux" ) ]]; then
    VROOT="$CAND"
  elif [[ -d /mnt/e/Bootloaders || -d /mnt/e/Linux ]]; then
    VROOT=/mnt/e
  else
    VROOT="$(cd "$REPO_ROOT/../.." && pwd)"
  fi
fi

IMAGE="${IMAGE:-ventoy-iso-check:local}"
REBUILD="${REBUILD:-0}"

info "Repo:   $REPO_ROOT"
info "Ventoy: $VROOT"
info "Image:  $IMAGE"

if ! command -v docker >/dev/null 2>&1; then
  err "Docker no está instalado o no está en el PATH."
  err "Instala Docker y vuelve a intentar. Sin Docker este script no ejecuta nada."
  exit 3
fi

if ! docker info >/dev/null 2>&1; then
  err "Docker daemon no responde. Inicia el servicio / Docker Desktop."
  exit 3
fi
info "Docker OK"

if [[ "$REBUILD" == "1" ]] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  info "Construyendo imagen…"
  docker build -t "$IMAGE" "$REPO_ROOT"
else
  info "Imagen ya presente (REBUILD=1 para reconstruir)"
fi

# Default: menú interactivo (como en PowerShell)
if [[ "${MENU:-1}" == "1" && "$#" -eq 0 ]]; then
  set -- menu
elif [[ "$#" -eq 0 ]]; then
  set -- scan --sort age
fi

info "docker run --rm -v $VROOT:/ventoy $IMAGE $*"
# -t solo si hay TTY
TTY_FLAGS=(-i)
if [[ -t 0 && -t 1 ]]; then
  TTY_FLAGS=(-it)
fi
exec docker run --rm "${TTY_FLAGS[@]}" -v "$VROOT:/ventoy" -e VENTOY_ROOT=/ventoy "$IMAGE" "$@"
