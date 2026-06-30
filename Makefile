DB_NAME ?= info_agent
DB_USER ?= postgres
DB_PASSWORD ?= postgres
DB_HOST ?= localhost

# TypeScript エージェント（フロントエンド）
AGENT_DIR ?= agent

.PHONY: dev db-migrate test install superuser db-start db-stop db-reset db-logs \
	agent-install agent dev-all reembed

db-start:
	docker compose up -d
	until docker compose exec db pg_isready -U $(DB_USER) -q; do sleep 1; done
	docker compose exec db psql -U $(DB_USER) -d $(DB_NAME) -c "CREATE EXTENSION IF NOT EXISTS vector;"

db-stop:
	docker compose down

db-reset:
	docker compose down -v

db-logs:
	docker compose logs -f db

db-migrate:
	DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py migrate

install:
	uv venv && uv pip install -r requirements.txt

superuser:
	DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py createsuperuser

server:
	DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py runserver

# エージェント（Bun）の依存をインストール
agent-install:
	cd $(AGENT_DIR) && bun install

# エージェント（フロントエンド）単体を起動（http://localhost:3000）
agent:
	cd $(AGENT_DIR) && bun run dev

# バックエンド（Django :8080）とエージェント（Bun :3000）を同時起動する。
# 前提として db-start を依存に指定しているため、先にDB（Docker）が起動・準備完了する。
# Ctrl-C で両方をまとめて停止する（trap 'kill 0' でプロセスグループを終了）。
# 事前に agent/.env に OPENAI_API_KEY を設定しておくこと。
dev-all: db-start
	@echo "起動中: バックエンド (8080) とエージェント (3000)"
	@trap 'kill 0' INT TERM EXIT; \
		DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py runserver 8080 & \
		(cd $(AGENT_DIR) && bun run dev) & \
		wait

test:
	uv run python manage.py test knowledge_base --settings=config.test_settings

# 既存チャンクをファイル名コンテキスト付きで再ベクトル化する（contextual embedding 導入後に一度実行）
reembed:
	DB_PASSWORD=$(DB_PASSWORD) uv run python manage.py reembed
