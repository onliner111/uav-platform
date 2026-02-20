COMPOSE_FILE := infra/docker-compose.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)

DB_PORT ?= 5432
REDIS_PORT ?= 6379
APP_PORT ?= 8000
APP_BASE_URL ?= http://app:8000

export DB_PORT
export REDIS_PORT
export APP_PORT

.PHONY: up down logs lint typecheck test migrate openapi openapi-smoke e2e verify-phase0

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down -v --remove-orphans

logs:
	$(COMPOSE) logs -f app db redis

lint:
	$(COMPOSE) run --rm app ruff check app tests infra/scripts

typecheck:
	$(COMPOSE) run --rm app mypy app

test:
	$(COMPOSE) run --rm app pytest

migrate:
	$(COMPOSE) up -d db
	$(COMPOSE) run --rm app alembic upgrade head

openapi:
	rm -rf openapi/clients/python openapi/postman
	mkdir -p openapi/clients/python openapi/postman
	$(COMPOSE) run --rm --build app-tools python -m app.infra.openapi_export
	$(COMPOSE) run --rm openapi-generator generate \
		-i /work/openapi/openapi.json \
		-g python \
		-o /work/openapi/clients/python \
		--skip-validate-spec
	$(COMPOSE) run --rm openapi-generator generate \
		-i /work/openapi/openapi.json \
		-g postman-collection \
		-o /work/openapi/postman \
		--skip-validate-spec

openapi-smoke:
	$(COMPOSE) up -d app
	$(COMPOSE) run --rm --build -e APP_BASE_URL=$(APP_BASE_URL) app-tools python infra/scripts/verify_openapi_client.py

e2e: up migrate openapi
	$(COMPOSE) run --rm --build -e APP_BASE_URL=$(APP_BASE_URL) app-tools python infra/scripts/demo_e2e.py
	$(COMPOSE) run --rm --build -e APP_BASE_URL=$(APP_BASE_URL) app-tools python infra/scripts/verify_smoke.py

verify-phase0: up lint typecheck test migrate
	$(COMPOSE) run --rm -e APP_BASE_URL=$(APP_BASE_URL) app python infra/scripts/verify_smoke.py
