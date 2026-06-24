# 設計意図・技術選定理由

## 想定ユーザーと業務シナリオ

### 誰が使うか

社内にドキュメントが蓄積されている組織の従業員。
具体的には以下のような役割を想定しています。

| ロール | 利用シーン |
|---|---|
| 人事担当者 | 応募者の職歴書・履歴書を横断検索して候補者情報を確認する |
| 新入社員 | 大量のマニュアル・規程文書から「〇〇の手順は？」と自然言語で質問する |
| エンジニア | 技術仕様書や設計ドキュメントから関連箇所を素早く探し出す |
| 営業担当者 | 提案資料・報告書から過去の事例や数値を検索して引用する |
| 一般社員 | ファイル名や格納場所を覚えていなくても、内容の断片から目的の資料にたどり着ける |

### いつ・どの業務で使うか

- **情報検索の非効率さ解消**: ドキュメントが数十〜数百件になると、目視での検索は現実的でない。本システムは「資料があることは知っているが、どこに書いてあるかわからない」という問題を解決する
- **オンボーディング短縮**: 新入社員が社内規程や操作手順を自然言語で質問できるため、先輩社員への質問コストを削減できる
- **採用フロー支援**: 人事が「Aさんの職歴書はあるか？」と入力するだけでファイル名ベースの検索も含めて横断検索できる

---

## AI API・モデルの選定理由

### OpenAI API を選択した理由

| 観点 | 理由 |
|---|---|
| **Function Calling の成熟度** | OpenAI の Function Calling は仕様・ドキュメントが整備されており、`tool_choice: "auto"` で LLM が自律的にツールを選択・実行できる。本課題の核心である「エージェントループの自前実装」に適した API 設計になっている |
| **OpenAI 互換エンドポイント対応** | `OPENAI_BASE_URL` を設定することで Groq・Ollama・Azure OpenAI などの互換エンドポイントに切り替えられる。ベンダーロックインを避けた実装になっている |

### 埋め込みモデルに `paraphrase-multilingual-MiniLM-L12-v2` を選択した理由

- **多言語対応**: 日本語・英語が混在する社内文書に対して、英語で質問しても日本語文書を検索できる（逆も同様）
- **ローカル実行**: API コストが発生しない。オフライン環境でも動作する
- **384 次元**: ストレージ効率と検索精度のバランスが良く、pgvector のインデックスが軽量に動作する

---

## アーキテクチャの設計意図

### Python 検索層 ＋ TypeScript エージェント層の二層構造にした理由

```
[TypeScript Agent :3000]  ←REST→  [Django Knowledge Base :8080]  ←→  [pgvector]
```

**分離した理由:**

| 層 | 言語選択の理由 |
|---|---|
| **検索層（Python）** | `sentence-transformers` など NLP・ドキュメント処理のエコシステムが Python に集中している。ベクトル埋め込みの生成はこれらのライブラリを直接使うのが最も効率的であり、将来的なファイル形式の拡張にも対応しやすい |
| **エージェント層（TypeScript）** | ユーザーが自然言語で気軽に質問できる UI を提供することを重視した。Hono による軽量な Web サーバー、検索クエリを意識させずに知識ベースへアクセスできる体験を実現している |

**REST API で繋いだ理由:**

- 将来的にエージェント側を別サービスに差し替えても検索 API はそのまま再利用できる
- テスト時に検索層・エージェント層を独立して動作確認できる（`make test` は Docker 不要で実行できる）

### MCP Server を実装した理由

[`agent/src/mcp-server.ts`](agent/src/mcp-server.ts) に MCP（Model Context Protocol）サーバーを実装しています。

- Claude Desktop などの MCP 対応クライアントから、本ナレッジベースを直接ツールとして呼び出せる
- Agent Web UI（Hono）と MCP Server を同じ TypeScript コードベースに共存させることで、一つのツール定義（[`agent/src/tools/registry.ts`](agent/src/tools/registry.ts)）を両方の経路で再利用できる構造になっている

---

## エージェントの思考プロセスのログ出力

エージェントがツールを呼び出すたびに、サーバーコンソールに以下の形式でログを出力します（[`agent/src/agent.ts:142`](agent/src/agent.ts#L142)）。

```
[tool-call]   search_knowledge_base  args={"query":"入社手続き","category":""}
[tool-result] search_knowledge_base  ok size=1842
[tool-call]   list_documents         args={}
[tool-result] list_documents         ok size=634
```

これにより、LLM がどのツールをどの順番・引数で呼び出したかをリアルタイムで追跡できます。

---

## データベースアーキテクチャ

### ER 図

```
┌──────────────────────────────────────┐
│             Document                 │
├──────────────────────────────────────┤
│  id            BIGINT        (PK)    │
│  filename      VARCHAR(255)          │
│  category      VARCHAR(64)           │
│  file          VARCHAR               │
│  uploaded_at   TIMESTAMPTZ           │
│  status        VARCHAR(20)           │
│  error_message TEXT                  │
│  chunk_count   INT  DEFAULT 0        │
└─────────────────┬────────────────────┘
                  │  1 : n  CASCADE DELETE
┌─────────────────┴────────────────────┐
│               Chunk                  │
├──────────────────────────────────────┤
│  id            BIGINT        (PK)    │
│  document_id   BIGINT        (FK)    │
│  content       TEXT                  │
│  embedding     VECTOR(384)           │
│  position      INT                   │
└──────────────────────────────────────┘
```

### テーブル定義

#### knowledge_base_document

| カラム | 型 | 説明 |
|---|---|---|
| `id` | `BIGINT` (PK) | 自動採番主キー |
| `filename` | `VARCHAR(255)` | PDF ファイル名 |
| `category` | `VARCHAR(64)` | 分類（resume / manual / policy / technical / report / other） |
| `file` | `VARCHAR` | PDF 保存パス（`media/pdfs/{category}/{filename}`） |
| `uploaded_at` | `TIMESTAMPTZ` | アップロード日時（auto_now_add） |
| `status` | `VARCHAR(20)` | 処理状態（pending / processing / complete / failed） |
| `error_message` | `TEXT` | 処理失敗時のエラー内容 |
| `chunk_count` | `INT` | 処理完了後のチャンク総数（デフォルト 0） |

#### knowledge_base_chunk

| カラム | 型 | 説明 |
|---|---|---|
| `id` | `BIGINT` (PK) | 自動採番主キー |
| `document_id` | `BIGINT` (FK) | Document への外部キー（CASCADE DELETE） |
| `content` | `TEXT` | テキスト内容 |
| `embedding` | `VECTOR(384)` | 384 次元ベクトル（pgvector） |
| `position` | `INT` | ドキュメント内の順序（0 始まり） |

### pgvector 設定

| 項目 | 値 |
|---|---|
| PostgreSQL バージョン | 17（`pgvector/pgvector:pg17`） |
| pgvector バージョン | 0.4.2 |
| ベクトル次元 | 384 |
| 距離計算 | コサイン距離（CosineDistance） |
| 検索距離しきい値 | `SEARCH_MAX_DISTANCE`（デフォルト 1.0） |
| 埋め込みモデル | paraphrase-multilingual-MiniLM-L12-v2 |

### ファイルストレージ構造

アップロードされた PDF はカテゴリ別に `media/` 以下に保存されます。

```
media/
└── pdfs/
    ├── resume/          # 職歴書・履歴書
    ├── manual/          # 操作マニュアル
    ├── policy/          # 規程・ポリシー
    ├── technical/       # 技術資料
    ├── report/          # レポート・報告書
    ├── other/           # その他
    └── uncategorized/   # 分類なし
```
