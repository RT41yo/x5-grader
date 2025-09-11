# Makefile для удобства работы с проектом

COMPOSE = docker-compose

.PHONY: up down logs ps rebuild migrate seed

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

rebuild:
	$(COMPOSE) up -d --build

migrate:
	$(COMPOSE) exec api alembic upgrade head

seed:
	$(COMPOSE) exec api python -m app.scripts.seed_data
