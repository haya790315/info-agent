# RAG Agent

PDF ドキュメントを知識ベースとして活用する、AI 対話型ナレッジ管理システムです。  
Django による RAG（Retrieval-Augmented Generation）バックエンドと、TypeScript/Bun による AI エージェントフロントエンドの二層構造で構成されています。

---

## 概要

このプロジェクトは以下の 2 つのサービスで構成されています。

| サービス | 技術 | ポート | 役割 |
|---|---|---|---|
| **知識ベース（バックエンド）** | Python / Django | 8080 | PDF アップロード・テキスト抽出・ベクトル検索 |
| **AI エージェント（フロントエンド）** | TypeScript / Bun / Hono | 3000 | LLM による自然言語対話・ツール呼び出し |
| **データベース** | PostgreSQL 17 + pgvector | 5432 | ベクトルデータの永続化 |

### システムアーキテクチャ

```
ユーザー
  │
  ▼
[Agent Service :3000]  ←→  OpenAI API (LLM)
  │  Hono Web + Agent Loop
  │  Function Calling で以下のツールを呼び出す:
  │   - search_knowledge_base
  │   - list_documents
  │   - get_document_detail
  ▼
[Knowledge Base API :8080]  ←→  PostgreSQL + pgvector
  │  Django REST API
  │   - /api/search/
  │   - /api/documents/
  │   - /api/documents/<id>/
  ▼
[pgvector DB :5432]
  └─ Document / Chunk モデル（384 次元ベクトル）
```

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| AI エージェント | TypeScript + Bun + Hono |
| LLM 推論 | OpenAI API(gpt-5.4-mini) |
| バックエンド検索 | Django 6.0 |
| 埋め込みモデル | sentence-transformers（paraphrase-multilingual-MiniLM-L12-v2, 384 次元） |
| ベクトルデータベース | PostgreSQL 17 + pgvector |
| Web UI（知識ベース） | HTML + HTMX |
| パッケージ管理 | uv（Python）/ Bun（Node.js） |
| コンテナ | Docker Compose |

---

## 開発環境のセットアップ

### 前提条件

以下のツールを事前にインストールしてください。

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [uv](https://docs.astral.sh/uv/) — Python パッケージ管理ツール
- [Bun](https://bun.sh/) — JavaScript ランタイム / パッケージマネージャ

### 1. リポジトリのクローン

```bash
git clone https://github.com/haya790315/info-agent.git
cd info-agent
```

### 2. Python 依存パッケージのインストール

```bash
make install
```

`.venv/` ディレクトリが作成され、`requirements.txt` のパッケージがインストールされます。

> 初回インストール時に `sentence-transformers` が約 90MB のモデルファイルをダウンロードします。

### 3. Node.js 依存パッケージのインストール

```bash
make agent-install
```

`agent/node_modules/` にパッケージがインストールされます。

### 4. 環境変数の設定

Agent サービス用の `.env` ファイルを作成します。

```bash
cp agent/.env.example agent/.env
```

`agent/.env` を編集して必要な値を設定してください。

```dotenv
# OpenAI API キー（必須）
OPENAI_API_KEY=sk-...

# 使用するモデル（省略時: gpt-5.4-mini）
OPENAI_MODEL=gpt-5.4-mini

# OpenAI 互換エンドポイント（省略可）
OPENAI_BASE_URL=

# Django API のベース URL（dev-all 使用時はそのまま）
KB_API_BASE_URL=http://localhost:8080

# ベクトル検索の距離しきい値（小さいほど厳密）
SEARCH_MAX_DISTANCE=1.0
```

> **注意:** `OPENAI_API_KEY` は必須です。設定しないと Agent サービスが起動しません。

### 5. データベースの起動とマイグレーション

```bash
# PostgreSQL コンテナを起動し、pgvector 拡張を有効化
make db-start

# Django のマイグレーションを実行
make db-migrate
```

### 6. 開発サーバーの起動

バックエンドとフロントエンドを同時に起動する場合（推奨）：

```bash
make dev-all
```

個別に起動する場合：

```bash
# ターミナル 1: Django バックエンド（:8000）
make server

# ターミナル 2: AI エージェント（:3000）
make agent
```

### 動作確認

| URL | 内容 |
|---|---|
| `http://localhost:3000` | AI エージェント チャット画面 |
| `http://localhost:8080` | 知識ベース Web UI（PDF アップロード・検索） |
| `http://localhost:8080/admin/` | Django 管理画面（要スーパーユーザー） |

---

## 各サービスの使い方

### 知識ベース（Django Web UI）

**PDF のアップロード**

1. `http://localhost:8080` にアクセス
2. アップロードフォームから PDF ファイルを選択して送信
3. 処理が完了すると、テキストが自動的にチャンク分割・ベクトル化されます

> テキストが埋め込まれていない画像型 PDF は処理失敗になります。

**ドキュメントのステータス**

| ステータス | 説明 |
|---|---|
| 等待処理 | キュー待機中 |
| 処理中 | テキスト抽出・ベクトル化中 |
| 処理完了 | 完了（チャンク数を表示） |
| 処理失敗 | 失敗（エラー内容を表示） |

**セマンティック検索**

1. 検索フォームにキーワードや質問文を入力
2. pgvector の余弦類似度検索で関連するテキストチャンクが返されます

**管理画面**

```bash
# スーパーユーザーを作成
make superuser
```

`http://localhost:8080/admin/` からドキュメント・チャンクの管理が可能です。

---

### AI エージェント（Bun / Hono）

`http://localhost:3000` にアクセスすると、AI チャットインターフェースが表示されます。

エージェントは以下の 3 つのツールを LLM の Function Calling で自動的に使い分けます。

| ツール | 機能 |
|---|---|
| `search_knowledge_base` | 質問に関連するテキストチャンクをベクトル検索で取得 |
| `list_documents` | アップロード済みドキュメントの一覧を取得 |
| `get_document_detail` | 特定ドキュメントの詳細情報を取得 |

**使用例:**

```
「Aプロジェクトの仕様について教えてください」
「アップロードされているドキュメントの一覧を見せてください」
「○○に関する箇所を全て検索してください」
```

---

### REST API（Django）

知識ベースは以下の JSON API を提供します。Agent サービスから内部的に呼び出されます。

| メソッド | エンドポイント | 説明 |
|---|---|---|
| `GET` | `/api/search/?q=<クエリ>` | ベクトル類似度検索 |
| `GET` | `/api/documents/` | ドキュメント一覧 |
| `GET` | `/api/documents/<id>/` | ドキュメント詳細 |

**検索 API の例:**

```bash
curl "http://localhost:8080/api/search/?q=プロジェクト概要"
```

---

## Makefile コマンド一覧

### データベース操作

| コマンド | 説明 |
|---|---|
| `make db-start` | Docker で PostgreSQL を起動し、pgvector 拡張を有効化 |
| `make db-stop` | PostgreSQL コンテナを停止 |
| `make db-reset` | コンテナとボリュームを削除（**データも消去**） |
| `make db-logs` | データベースのログをリアルタイム表示 |

### セットアップ

| コマンド | 説明 |
|---|---|
| `make install` | Python 仮想環境を作成し、依存パッケージをインストール |
| `make db-migrate` | Django のデータベースマイグレーションを実行 |
| `make superuser` | Django 管理画面用のスーパーユーザーを作成 |
| `make agent-install` | Agent サービスの Bun パッケージをインストール |

### 開発サーバー起動

| コマンド | 説明 |
|---|---|
| `make server` | Django 開発サーバーを起動（:8000） |
| `make agent` | AI エージェントサービスを起動（:3000） |
| `make dev-all` | バックエンド（:8080）とエージェント（:3000）を同時起動（Ctrl-C で両方停止） |

### テスト・メンテナンス

| コマンド | 説明 |
|---|---|
| `make test` | Django ユニットテストを実行（SQLite メモリ DB 使用、Docker 不要） |
| `make reembed` | 既存チャンクのベクトルを再生成（埋め込みモデル変更後に実行） |

---

## プロジェクト構成

```
info-agent/
├── agent/                   # AI エージェントサービス（TypeScript/Bun）
│   ├── src/
│   │   ├── index.ts         # Hono Web サーバーエントリポイント
│   │   ├── agent.ts         # エージェントループ（Function Calling）
│   │   ├── llm.ts           # OpenAI API インテグレーション
│   │   ├── session.ts       # 会話セッション管理
│   │   ├── mcp-server.ts    # MCP サーバー実装
│   │   ├── config.ts        # 設定読み込み
│   │   └── tools/
│   │       ├── registry.ts  # ツール定義（3 ツール）
│   │       └── kbClient.ts  # 知識ベース REST クライアント
│   ├── .env.example         # 環境変数テンプレート
│   └── package.json
├── config/                  # Django プロジェクト設定
│   ├── settings.py
│   └── test_settings.py
├── knowledge_base/          # RAG コアアプリ（Django）
│   ├── models.py            # Document / Chunk モデル
│   ├── views.py             # Web UI ビュー
│   ├── api_views.py         # JSON REST API
│   ├── services/
│   │   ├── processor.py     # PDF テキスト抽出・チャンク分割
│   │   ├── embedder.py      # ベクトル埋め込み生成
│   │   └── searcher.py      # pgvector 類似度検索
│   └── templates/kb/        # HTMX テンプレート
├── media/pdfs/              # アップロード PDF の保存先
├── docker-compose.yml       # PostgreSQL + pgvector
├── Makefile                 # 開発コマンド
├── manage.py                # Django CLI
└── requirements.txt         # Python 依存パッケージ
```

---

## トラブルシューティング

**`make db-start` でコンテナが起動しない**

Docker Desktop が起動しているか確認してください。

```bash
docker info
```

**`make db-migrate` でデータベース接続エラーが発生する**

`make db-start` を先に実行してコンテナが起動していることを確認してください。

**Agent が「API key not found」エラーを返す**

`agent/.env` に `OPENAI_API_KEY` が正しく設定されているか確認してください。

**PDF アップロード後に検索結果が出ない**

PDF の処理には数秒かかります。ドキュメント一覧ページでステータスが `処理完了` になってから検索してください。

**既存データを再ベクトル化したい（埋め込みモデル変更後など）**

```bash
make reembed
```

---
