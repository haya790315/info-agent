DB_NAME ?= rag_agent
DB_USER ?= postgres
DB_PASSWORD ?= postgres
DB_HOST ?= localhost

.PHONY: dev migrate test install superuser db db-stop db-reset db-logs

db:
	docker compose up -d
	until docker compose exec db pg_isready -U $(DB_USER) -q; do sleep 1; done
	docker compose exec db psql -U $(DB_USER) -d $(DB_NAME) -c "CREATE EXTENSION IF NOT EXISTS vector;"

db-stop:
	docker compose down

db-reset:
	docker compose down -v

db-logs:
	docker compose logs -f db

install:
	uv venv && uv pip install -r requirements.txt

migrate:
	DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py migrate

superuser:
	DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py createsuperuser

dev:
	DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py runserver

test:
	uv run python manage.py test kb --settings=rag_agent.test_settings
