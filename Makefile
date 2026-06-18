DB_NAME ?= rag_agent
DB_USER ?= postgres
DB_PASSWORD ?= postgres
DB_HOST ?= localhost

# TypeScript エージェント（フロントエンド）
AGENT_DIR ?= agent

.PHONY: dev migrate test install superuser db db-stop db-reset db-logs \
	agent-install agent dev-all

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

# エージェント（Bun）の依存をインストール
agent-install:
	cd $(AGENT_DIR) && bun install

# エージェント（フロントエンド）単体を起動（http://localhost:3000）
agent:
	cd $(AGENT_DIR) && bun run dev

# バックエンド（Django :8080）とエージェント（Bun :3000）を同時起動する。
# Ctrl-C で両方をまとめて停止する（trap 'kill 0' でプロセスグループを終了）。
# 事前に `make db` でDBを起動し、agent/.env に OPENAI_API_KEY を設定しておくこと。
dev-all:
	@echo "起動中: バックエンド (8080) とエージェント (3000)"
	@trap 'kill 0' INT TERM EXIT; \
		DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py runserver 8080 & \
		(cd $(AGENT_DIR) && bun run dev) & \
		wait

test:
	uv run python manage.py test knowledge_base --settings=config.test_settings
