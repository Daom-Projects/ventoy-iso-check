IMAGE ?= ventoy-iso-check:local
VENTOY_HOST ?= /mnt/e

.PHONY: sync check scan links docker-build docker-check docker-scan help

help:
	@echo "make sync | scan | check | links | docker-build | docker-check"

sync:
	uv sync

scan:
	VENTOY_ROOT=$(VENTOY_HOST) uv run ventoy-iso-check scan $(VENTOY_HOST)

check:
	VENTOY_ROOT=$(VENTOY_HOST) uv run ventoy-iso-check check $(VENTOY_HOST) --urls

links:
	VENTOY_ROOT=$(VENTOY_HOST) uv run ventoy-iso-check links $(VENTOY_HOST) -o links.md

docker-build:
	docker build -t $(IMAGE) .

docker-scan:
	docker run --rm -v $(VENTOY_HOST):/ventoy $(IMAGE) scan

docker-check:
	docker run --rm -v $(VENTOY_HOST):/ventoy $(IMAGE) check --urls
