IMAGE ?= ventoy-iso-check:local
VENTOY_HOST ?= /mnt/e

.PHONY: sync check scan links test docker-build docker-check docker-scan docker-smoke help

help:
	@echo "make sync | test | scan | check | links | docker-build | docker-smoke | docker-check"

sync:
	uv sync

test:
	uv run pytest -q

scan:
	VENTOY_ROOT=$(VENTOY_HOST) uv run ventoy-iso-check scan $(VENTOY_HOST)

check:
	VENTOY_ROOT=$(VENTOY_HOST) uv run ventoy-iso-check check $(VENTOY_HOST) --urls

links:
	VENTOY_ROOT=$(VENTOY_HOST) uv run ventoy-iso-check links $(VENTOY_HOST) -o links.md

docker-build:
	docker build -t $(IMAGE) .

# Smoke sin montar disco (útil en CI local)
docker-smoke: docker-build
	docker run --rm $(IMAGE) -V
	docker run --rm $(IMAGE) --help

docker-scan:
	docker run --rm -v $(VENTOY_HOST):/ventoy $(IMAGE) scan

docker-check:
	docker run --rm -v $(VENTOY_HOST):/ventoy $(IMAGE) check --urls
