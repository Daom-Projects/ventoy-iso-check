#!/bin/sh
set -eu

# Raíz del volumen Ventoy dentro del contenedor
export VENTOY_ROOT="${VENTOY_ROOT:-/ventoy}"

if [ ! -d "$VENTOY_ROOT" ]; then
  echo "ERROR: VENTOY_ROOT no es un directorio: $VENTOY_ROOT" >&2
  echo "Monta tu partición Ventoy, p. ej.:" >&2
  echo "  docker run --rm -v E:\:/ventoy ventoy-iso-check:local check" >&2
  exit 2
fi

# Sin subcomando → menú (si TTY) vía CLI; si no, ayuda
if [ "$#" -eq 0 ]; then
  set -- menu
fi

exec ventoy-iso-check "$@"
