## Pipelab — everything runs in Docker.
##   make up            build and start on http://localhost:8080
##   make up GPU=1      same, with NVIDIA GPU access
##   make dev           hot-reload mode (UI on http://localhost:5173)
##   make test          backend, frontend and browser end-to-end suites (and linters)
##   make test-rust     compile and run the Rust exports (cargo, crates cached in a volume)

export PIPELAB_UID ?= $(shell id -u)
export PIPELAB_GID ?= $(shell id -g)

COMPOSE_FILES := -f docker-compose.yml
ifeq ($(GPU),1)
COMPOSE_FILES += -f docker-compose.gpu.yml
endif
ifeq ($(DEVICES),1)
COMPOSE_FILES += -f docker-compose.devices.yml
endif
ifeq ($(DEV),1)
COMPOSE_FILES += -f docker-compose.dev.yml
endif
COMPOSE := docker compose $(COMPOSE_FILES)

.PHONY: help build up dev down restart logs ps test test-backend test-frontend test-e2e test-rust shell clean-cache

help:
	@grep -E '^##' Makefile | sed 's/^## \{0,1\}//'

data:
	mkdir -p data

build:
	$(COMPOSE) build

up: data
	$(COMPOSE) up -d --build
	@echo "Pipelab is starting on http://localhost:$${PIPELAB_PORT:-8080}"

dev: data
	$(MAKE) up DEV=1

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

test: test-backend test-frontend test-e2e

test-backend:
	$(COMPOSE) --profile test run --rm --build api-test

test-rust:
	$(COMPOSE) --profile test build api-test
	$(COMPOSE) --profile test run --rm --build rust-check

test-frontend:
	$(COMPOSE) --profile test run --rm --build web-test

test-e2e: data
	mkdir -p e2e/test-results
	$(COMPOSE) --profile test run --rm --build e2e

shell:
	$(COMPOSE) exec api bash

clean-cache:
	rm -rf data/cache
