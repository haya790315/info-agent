# 研究与设计决策：pdf-knowledge-base

## 摘要

- **功能**：`pdf-knowledge-base`
- **发现范围**：新功能（Greenfield）
- **关键发现**：
  - `pgvector` Python 包提供 Django ORM 原生集成（VectorField、CosineDistance），无需自定义 SQL
  - PyMuPDF v1.23+ 存在多种异常类型，捕获 `Exception` 比仅捕获 `FileDataError` 更可靠
  - sentence-transformers 模型应作为模块级单例加载（约 90MB），`normalize_embeddings=True` 使 CosineDistance 结果一致

---

## 研究日志

### pgvector Django 集成

- **背景**：需要在 Django ORM 中存储和查询 384 维嵌入向量
- **来源**：pgvector-python GitHub 文档、pgvector Django 使用示例
- **发现**：
  - 安装：`pip install pgvector`
  - Migration 顺序要求：`VectorExtension()` 操作必须在任何包含 `VectorField` 的 migration 之前运行
  - 查询：`Chunk.objects.order_by(CosineDistance('embedding', vector))[:5]`
  - CosineDistance 值域 [0, 2]，升序排列 = 最相似在前
  - 生产场景推荐 HNSW 索引，但学习项目数据量不需要
- **影响**：Migration 拆为两步（先扩展，再建表）

### sentence-transformers all-MiniLM-L6-v2

- **背景**：需要本地嵌入模型，不依赖付费 API
- **发现**：
  - 输出维度：384
  - 首次使用时下载约 90MB 权重
  - `_model = SentenceTransformer("all-MiniLM-L6-v2")` 应在模块级定义，避免每次请求重新加载
  - `encode(texts, normalize_embeddings=True)` 返回 L2 归一化向量，与余弦相似度搜索一致
  - 返回 numpy array，需 `.tolist()` 转为 Python list 存入 VectorField
- **影响**：EmbedderService 使用模块级单例；`normalize_embeddings=True` 作为默认参数

### PyMuPDF 异常处理

- **背景**：需要处理无效/图像型 PDF
- **发现**：
  - 从字节流打开：`pymupdf.open(stream=pdf_bytes, filetype="pdf")`
  - v1.23+ 版本中某些格式错误抛出 `pymupdf.mupdf.FzErrorFormat` 而非 `FileDataError`（GitHub issue #3905）
  - 图像型 PDF `page.get_text()` 返回空字符串，不抛异常
  - 建议：捕获 `Exception` 作为兜底，避免版本差异导致未捕获异常
- **影响**：ProcessorService 使用 `except Exception`；空文本由调用方（UploadView）检测并设 status=failed

### HTMX 请求检测

- **背景**：SearchView 需要对 HTMX 请求返回局部模板，对普通请求返回完整页面
- **发现**：
  - Option A：`pip install django-htmx` → `request.htmx` 布尔值（推荐，有类型支持）
  - Option B：原生检查 `request.headers.get("HX-Request") == "true"`
  - Option B 无额外依赖，对本项目已足够
- **影响**：采用 Option B，不引入 `django-htmx` 包

---

## 架构模式评估

| 选项 | 描述 | 优势 | 风险 / 局限 | 备注 |
|------|------|------|------------|------|
| 单 app 平铺 | models/views/utils 全部在 kb/ 根目录 | 最简单 | pipeline 步骤混在 utils.py 中，学习边界不清晰 | 被拒绝 |
| 服务层（选定） | kb/services/ 下独立 processor/embedder/searcher | 各步骤职责清晰，对应学习目标；Phase 2 只需加 llm.py | 略多一层，但对学习有价值 | 选定 |
| 多 app 拆分 | documents + search 两个 Django app | Django 大项目最佳实践 | 过度设计，学习项目不需要 | 被拒绝 |

---

## 设计决策

### 决策：同步 ingestion（不使用 Celery）

- **背景**：PDF 处理耗时（提取+嵌入），是否应异步化
- **备选方案**：
  1. 同步阻塞 — 上传 POST 等待 ingestion 完成再 redirect
  2. Celery 异步 — 上传立即返回，后台任务处理
- **选定方案**：同步阻塞
- **理由**：brief.md 明确约束"不引入异步队列"；学习项目文件小，阻塞时间可接受；避免 Celery 配置复杂度干扰学习目标
- **权衡**：大文件或高并发时用户等待时间长；Phase 2 若需异步可替换为 Celery task
- **后续**：Phase 2 扩展时考虑将 ingestion 拆为 Celery task

### 决策：PDF 不持久化存储

- **背景**：是否需要保留原始 PDF 文件以支持重新处理
- **备选方案**：
  1. 不保留 — 处理完成后丢弃字节流
  2. 保留 — 存储到 MEDIA_ROOT / S3
- **选定方案**：不保留
- **理由**：brief.md 范围中无"重新处理"需求；省去 MEDIA 配置复杂度；Phase 1 学习目标是理解向量存储，不是文件管理
- **权衡**：无法重新处理已上传文档；如需此功能需在 Phase 2 补充 FileField

### 决策：normalize_embeddings=True

- **背景**：存储前是否对向量归一化
- **选定方案**：`normalize_embeddings=True`
- **理由**：pgvector CosineDistance 在归一化向量上等价于内积，结果一致且不受向量长度影响
- **后续**：如更换相似度指标为 L2，需同步调整此参数

---

## 风险与缓解

- **首次加载延迟**：sentence-transformers 模型首次下载约 90MB，首次请求慢 → 使用模块级单例后续请求无影响；本地学习项目可接受
- **PyMuPDF 版本差异**：异常类型在 v1.23+ 有变化 → 捕获 `Exception` 而非具体子类
- **Migration 顺序错误**：VectorField 在 VectorExtension 之前运行会失败 → 0001/0002 命名强制顺序，文档中注明
- **空文本 PDF**：图像型 PDF `get_text()` 返回 '' → UploadView 检测空文本并设 status=failed，不尝试嵌入

---

## 参考资料

- pgvector-python GitHub: https://github.com/pgvector/pgvector-python
- sentence-transformers all-MiniLM-L6-v2: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- PyMuPDF 文档: https://pymupdf.readthedocs.io/
- pgvector Django 示例（官方）: pgvector-python/examples/django_example/

---

# ギャップ分析：REST API + 原本ファイル保存（要件 8〜11）

> 2026-06-18 追記。既存の検索層（要件 1〜7）は実装・テスト済み。本節は新規追加スコープ（JSON API と原本 PDF 保存・閲覧リンク）のみを対象とする。

## 1. 現状調査（既存資産）

| 資産 | 場所 | 新スコープでの再利用性 |
|------|------|------------------------|
| `searcher.search(vector, top_k=5)` | `knowledge_base/services/searcher.py` | **そのまま再利用可**。`select_related('document')` 済みなので、各 Chunk から `chunk.document.filename` を追加クエリなしで取得できる（要件 8） |
| `embedder.embed_one(text)` | `knowledge_base/services/embedder.py` | **そのまま再利用可**（要件 8 のクエリ埋め込み） |
| `Document` モデル | `knowledge_base/models.py:10` | `filename / uploaded_at / status / error_message / chunk_count` を保持。**原本ファイルのフィールドは無し** → 要件 11 で拡張が必要 |
| `UploadView.post()` | `knowledge_base/views.py:28` | `file.read()` でバイト列を取得後、**原本ファイルを破棄**している。要件 11 で保存処理の追加が必要（唯一の ingestion 経路なので拡張は不可避） |
| `get_object_or_404(Document, pk=pk)` | `knowledge_base/views.py:130` | 詳細取得パターンを API 版（要件 10）でも踏襲できる |
| URL 設定 | `knowledge_base/urls.py`（`app_name='knowledge_base'`、ルートにマウント） | 新規 API ルートを追加する余地あり |
| 設定 | `config/settings.py` | `STATIC_URL` のみ。**`MEDIA_URL` / `MEDIA_ROOT` 未設定** → 要件 11 のファイル保存で追加が必要 |
| 依存 | `requirements.txt` | Django / pgvector / PyMuPDF / sentence-transformers のみ。**DRF 無し** → API は組み込み `JsonResponse` で実装するのが既存方針に整合 |

## 2. 要件 → 資産マッピング（ギャップタグ：再利用 / 不足 / 制約）

### 要件 8：セマンティック検索 API
- ✅ **再利用**：`embedder.embed_one` + `searcher.search`（検索ロジックは完全に既存）
- 🔴 **不足**：JSON エンドポイント（ビュー）、Chunk → `{content, filename, ファイルリンク}` のシリアライズ
- 🔗 **依存**：レスポンス内の「原本リンク」は要件 11 の成果物に依存

### 要件 9：ドキュメント一覧 API
- ✅ **再利用**：`Document.objects.all()`（Meta で `-uploaded_at` 順）
- 🔴 **不足**：JSON ビュー + 各 Document のシリアライズ（id / filename / status / chunk_count / リンク）

### 要件 10：ドキュメント詳細 API
- ✅ **再利用**：`get_object_or_404` パターン
- 🔴 **不足**：JSON ビュー、存在しない pk に対する **JSON 形式の 404**（既存の HTML 404 とは別経路）

### 要件 11：原本ファイル保存・閲覧
- 🔴 **不足（モデル）**：`Document` に `FileField`（例：`file`）追加 → **マイグレーション必要**
- 🔴 **不足（設定）**：`MEDIA_URL` / `MEDIA_ROOT`
- 🔴 **不足（保存処理）**：`UploadView` で原本を保存
- ⚠️ **制約（読み取り順序）**：現在 `file.read()` で 1 回読み切っている。`FileField` 保存と抽出用バイト取得が競合する。アップロードファイルは 1 回しか読めない（`InMemoryUploadedFile` / `TemporaryUploadedFile`）ため、**保存 → 再オープン**、または **`read()` 後に `seek(0)`** のいずれかが必要 → 設計で確定（Research Needed）
- 🔴 **不足（配信）**：「安定した閲覧リンク」の提供方式（MEDIA 直配信 or 専用ダウンロードビュー）
- 🔗 **波及**：要件 5.5（詳細ページにリンク表示）= `document_detail.html` テンプレート拡張

## 3. 実装アプローチの選択肢

新規スコープは性質の異なる 2 種に分かれる：**(A) 原本ファイル保存**（既存モデル/アップロード経路の拡張が不可避）と **(B) JSON API 層**（新規が自然）。

### Option A：既存 views.py に API を相乗り
- HTML ビューと JSON ビューを同一ファイル/同一ビューに混在
- ❌ HTML と JSON の責務が混ざり、`render` 経路と `JsonResponse` 経路が交錯。可読性低下

### Option B：API を独立モジュール化（推奨の片翼）
- `knowledge_base/api_views.py`（または `views/api.py`）+ シリアライズ補助関数を新設、`urls.py` に `/api/...` を追加
- ✅ HTML（HTMX）層と JSON 層をクリーンに分離。テストも独立
- ❌ ファイル数増

### Option C：ハイブリッド（推奨）
- **保存（要件 11 の永続化）**：`Document` モデル + `UploadView` を**拡張**（唯一の ingestion 経路のため選択肢なし）+ `settings` に MEDIA 追加
- **API（要件 8/9/10）**：**新規モジュール**（Option B）として追加
- **配信（要件 11 のリンク）**：MEDIA 直配信 or 専用 `FileResponse` ビュー（設計で確定）
- ✅ 各責務が最も自然な場所に収まる。既存の検索層・HTMX 層は無改変

## 4. 工数・リスク

| 項目 | 工数 | リスク | 根拠 |
|------|------|--------|------|
| JSON API 層（要件 8/9/10） | **S** | **Low** | 検索ロジックは既存再利用、`JsonResponse` のみ。シリアライズは単純 |
| 原本ファイル保存（要件 11 保存） | **S〜M** | **Low〜Medium** | `FileField` + マイグレーション + MEDIA 設定は定型。ただし**ファイル読み取り順序**の落とし穴あり |
| ファイル配信・リンク（要件 11 配信 + 要件 5.5） | **S** | **Low** | dev は MEDIA 配信、堅めにするなら `FileResponse` ビュー。`document_detail.html` 微修正 |

総合：**S〜M / Low〜Medium**。アーキテクチャ変更なし、既存パターンの延長。

## 5. 設計フェーズへの申し送り（Research Needed）

1. **アップロード時のファイル読み取り順序**：`FileField` 保存と抽出用 `read()` の競合。保存 → `doc.file.open()` で再読込 する案が有力。`InMemoryUploadedFile` / `TemporaryUploadedFile` 双方で検証
2. **ファイル配信方式**：MEDIA 直配信（`django.views.static.serve` / 開発時）vs 専用 `FileResponse` ダウンロードビュー。「安定リンク」（要件 11.4）の URL 形を決める
3. **リンクの絶対 URL 化**：API 消費者（TS Agent / ブラウザ）が直接開けるよう、`request.build_absolute_uri()` で絶対 URL を返すか、相対パスを返すか
4. **API の URL 構造**：`/api/search/`（POST）、`/api/documents/`（GET）、`/api/documents/<id>/`（GET）、原本配信 `/api/documents/<id>/file/`（or MEDIA URL 直結）。typescript-agent spec の Tool 契約と一致させること
5. **CORS / リクエスト形式**：TS Agent が別オリジン（Bun）から呼ぶ場合の CORS、POST ボディ形式（JSON vs form）。設計で方針決定

## 6. 推奨

- **アプローチ**：Option C（ハイブリッド）— 保存は既存拡張、API は新規モジュール
- **DRF は導入しない**：組み込み `JsonResponse` で十分、既存方針に整合
- **要件 11 を最初に実装**：API（要件 8/10）のリンク項目が依存するため、原本保存・リンク基盤を先に確定させると手戻りが少ない

---

# 設計合成（要件 8〜11）

> 2026-06-18。ライト・ディスカバリ + 合成の結果。ユーザー決定：**PDF はまずローカルに保存し、保存先（オブジェクトストレージ等）は後で扱う**。

## Build vs Adopt
- **採用**：Django 組み込み `FileField` + `FileSystemStorage`（ローカル `MEDIA_ROOT`）。**新規 pip 依存なし、DRF なし**。学習プロジェクトかつ「まずローカル保存」方針に最適
- **採用**：API は組み込み `JsonResponse` + `View`。既存ビューと同じ素の Django 流儀

## 簡素化（Simplification）
- **専用ダウンロードビューを作らない**：`FileField.url`（MEDIA_URL + パス）+ 開発時 MEDIA 配信（`static()` ヘルパ）で要件 11.2/11.4（原本配信 + 安定リンク）を満たす。本番向けの専用 `FileResponse` ビューは境界外（後続）
- **シリアライザ層を新設しない**：`api_views.py` 内のモジュール関数（`_document_dict` / `_chunk_dict` / `_file_url`）で十分。DRF Serializer は過剰

## 設計上の解決（Research Needed への回答）
1. **ファイル読み取り順序**：`pdf_bytes = file.read()` で 1 回だけ読み、`ContentFile(pdf_bytes)` で原本保存し、同じ `pdf_bytes` を `extract_text()` に渡す。再読込・`seek(0)` 不要、read-once 競合を回避
2. **配信方式**：ローカル `FileField` + 開発時 MEDIA 配信（上記簡素化）
3. **リンクの絶対 URL 化**：`request.build_absolute_uri(doc.file.url)` で絶対 URL を返す（TS Agent / ブラウザが直接開ける）。`file` 未設定時は `null`
4. **API URL 構造**：`/api/search/`（POST）、`/api/documents/`（GET）、`/api/documents/<int:pk>/`（GET）。原本は `file_url`（MEDIA URL）で参照、専用配信ルートは作らない
5. **CORS / CSRF**：
   - **CORS 不要**：Tool 呼び出しは Bun（サーバ）→ Django（サーバ）のサーバ間通信。原本リンクはブラウザのトップレベル遷移（XHR ではない）。いずれもブラウザ CORS の対象外
   - **CSRF**：検索 API（POST）はセッション認証を使わないサーバ間呼び出しのため `csrf_exempt`。学習プロジェクトで許容（認証は境界外）

## リスクと緩和
- **原本の重複・肥大**：`upload_to='pdfs/'` 配下に蓄積。学習用途で許容。クリーンアップは境界外
- **本番 MEDIA 配信**：`static()` は DEBUG 時のみ。本番は別途 Web サーバ設定が必要 → 「保存先は後で扱う」方針に合致、境界外として明記
- **既存行への影響**：`FileField(blank=True, null=True)` で追加。既存 Document 行・抽出失敗時も NULL 許容で破綻しない
