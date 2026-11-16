PYTHON ?= python
COMPOSE = docker compose -f tests/integration/docker/docker-compose.yml

.PHONY: help lint test-unit test-integration up-db down-db

help:
	@echo "lint               ruff check and format check"
	@echo "test-unit          pytest tests/unit"
	@echo "test-integration   pytest tests/integration (Oracle must be up)"
	@echo "up-db              start Oracle docker"
	@echo "down-db            stop Oracle docker"

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests

test-unit:
	$(PYTHON) -m pytest tests/unit --tb=short

test-integration:
	$(PYTHON) -m pytest tests/integration --tb=short

up-db:
	$(COMPOSE) up -d --wait --wait-timeout 600

down-db:
	$(COMPOSE) down -v
