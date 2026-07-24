#!/usr/bin/env sh
# Lanza ventoy-iso-check en Docker montando el volumen Ventoy en /ventoy.
# Uso:
#   ./scripts/run-docker.sh check
#   VENTOY_HOST=/mnt/e ./scripts/run-docker.sh links -o /ventoy/links.md
#   VENTOY_HOST=E:\ ./scripts/run-docker.sh scan   # Docker Desktop Windows

set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
HOST_VENTOY="${VENTOY_HOST:-${VENTOY_ROOT:-/mnt/e}}"
IMAGE="${VIC_IMAGE:-ventoy-iso-check:local}"

if [ "$#" -eq 0 ]; then
  set -- check
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Construyendo imagen $IMAGE …"
  docker build -t "$IMAGE" "$ROOT"
fi

exec docker run --rm -it \
  -e VENTOY_ROOT=/ventoy \
  -v "$HOST_VENTOY:/ventoy" \
  "$IMAGE" \
  "$@"
