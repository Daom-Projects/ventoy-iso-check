#!/usr/bin/env sh
set -eu

# Raíz del volumen Ventoy dentro del contenedor
export VENTOY_ROOT="${VENTOY_ROOT:-/ventoy}"

if [ ! -d "$VENTOY_ROOT" ]; then
  echo "ERROR: VENTOY_ROOT no es un directorio: $VENTOY_ROOT" >&2
  echo "Monta tu partición Ventoy, p. ej.:" >&2
  echo "  docker run --rm -v /ruta/al/ventoy:/ventoy ghcr.io/daom-projects/ventoy-iso-check check" >&2
  exit 2
fi

# Si no hay subcomando, mostrar ayuda
if [ "$#" -eq 0 ]; then
  set -- --help
fi

# Atajos: subcomandos con root opcional (usan VENTOY_ROOT del entorno)
case "${1:-}" in
  scan|check|links|download|export|suggest|bootloaders|ventoy|menu|meta)
    exec ventoy-iso-check "$@"
    ;;
  *)
    exec ventoy-iso-check "$@"
    ;;
esac
