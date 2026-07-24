# syntax=docker/dockerfile:1
# Imagen portable de ventoy-iso-check.
# Monta tu partición Ventoy en /ventoy.
#
#   docker build -t ventoy-iso-check:local .
#   docker run --rm -v /ruta/ventoy:/ventoy ventoy-iso-check:local check

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY catalog.yaml sisou.toml ./

# Instalar el proyecto en un venv local
RUN uv sync --frozen --no-dev \
    && /app/.venv/bin/ventoy-iso-check -V

# Intentar instalar sisou (download in-container). Si falla, scan/check/links siguen OK.
RUN uv pip install --python /app/.venv/bin/python "sisou>=2.4.1" \
    && /app/.venv/bin/sisou --version \
    || echo "WARN: sisou no instalado en la imagen; usa download en host con uv"

FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="ventoy-iso-check" \
      org.opencontainers.image.description="Inventario y actualización de ISOs en discos Ventoy" \
      org.opencontainers.image.source="https://github.com/Daom-Projects/ventoy-iso-check" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /bin/bash vic

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY catalog.yaml sisou.toml README.md LICENSE ./
COPY src ./src
COPY docker/entrypoint.sh /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    VENTOY_ROOT=/ventoy \
    VIRTUAL_ENV=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1

RUN chmod +x /entrypoint.sh \
    && mkdir -p /ventoy \
    && chown -R vic:vic /app /ventoy

# root por defecto para montajes host con permisos mixtos; se puede -u 1000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["check"]
