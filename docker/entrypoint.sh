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

# Atajos: `check` sin path usa VENTOY_ROOT
case "${1:-}" in
  scan|check|links|download)
    cmd="$1"
    shift
    # Si el usuario no pasó un path y el siguiente arg no es opción,
    # insertamos VENTOY_ROOT solo cuando no hay args de path.
    # Typer acepta root opcional; sin args usa default_ventoy_root() → VENTOY_ROOT.
    exec ventoy-iso-check "$cmd" "$@"
    ;;
  *)
    exec ventoy-iso-check "$@"
    ;;
esac
