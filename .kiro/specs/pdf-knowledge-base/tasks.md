# 实现计划

- [ ] 1. 基础设施：项目骨架与数据库配置
- [x] 1.1 创建 Django 项目骨架，安装依赖，配置基础模板
  - 初始化 Django 项目 `rag_agent` 和应用 `kb`（`startproject` + `startapp`）
  - 创建 `requirements.txt`，包含：`django`, `pgvector`, `PyMuPDF`, `sentence-transformers`, `psycopg2-binary`
  - 在 `settings.py` 中配置 PostgreSQL 数据库连接、`INSTALLED_APPS` 包含 `'kb'`
  - 创建 `kb/services/__init__.py`，建立服务层目录骨架
  - 创建含 HTMX CDN 引用的 `kb/templates/kb/base.html`，供三个页面模板继承
  - 在 `rag_agent/urls.py` 中 `include('kb.urls')`；在 `kb/urls.py` 中建立空 URL 配置（`app_name = 'kb'`）
  - 前置条件说明：本地需已安装 PostgreSQL 15+ 且 pgvector 扩展可用（`CREATE EXTENSION vector` 不报错）
  - 验证：`pip install -r requirements.txt` 成功；`python manage.py check` 无错误输出
  - _Requirements: 1.1_

- [x] 1.2 配置 pgvector 扩展并定义数据模型，生成迁移
  - 创建 `kb/migrations/0001_vector_extension.py`，包含 `VectorExtension()` migration 操作（必须早于 VectorField）
  - 创建 `kb/migrations/0002_initial.py`，定义 `Document`（filename、uploaded_at、status 含四状态 pending/processing/complete/failed、error_message、chunk_count）和 `Chunk`（document FK、content、embedding `VectorField(dimensions=384)`、position）
  - 验证：`python manage.py migrate` 成功执行；PostgreSQL 中 `kb_chunk.embedding` 列类型为 `vector(384)`
  - _Requirements: 2.3, 3.2, 4.2_

---

- [ ] 2. Core：Ingestion 服务层（三个服务可并行实现）
- [x] 2.1 (P) 实现文本提取与分块服务
  - 实现 `kb/services/processor.py`：`extract_text(pdf_bytes: bytes) -> str`，使用 `pymupdf.open(stream=pdf_bytes, filetype="pdf")` 逐页拼接文本，捕获所有异常向上抛出（图像型 PDF 返回空字符串）
  - 实现 `split_into_chunks(text: str, chunk_size: int = 1000) -> list[str]`，按固定字符数切分：`text` 为空时返回 `[]`；所有块按顺序拼接等于原始 `text`（无字符丢失）
  - 验证：`split_into_chunks('')` 返回 `[]`；1500 字符的字符串返回 2 个块；所有块拼接等于原文本
  - _Requirements: 2.1, 2.2, 3.1_
  - _Boundary: ProcessorService_

- [x] 2.2 (P) 实现嵌入向量生成服务
  - 实现 `kb/services/embedder.py`：模块级单例 `_model = SentenceTransformer("all-MiniLM-L6-v2")`（避免每次请求重新加载约 90MB 模型权重）
  - 实现 `embed_many(texts: list[str]) -> list[list[float]]`：调用 `_model.encode(texts, normalize_embeddings=True)`，返回 `.tolist()` 转换后的 Python 列表
  - 实现 `embed_one(text: str) -> list[float]`：单文本嵌入，复用 `embed_many`
  - 验证：`embed_one("test")` 返回长度为 384 的 float 列表；`embed_many(["a", "b"])` 返回长度为 2 的列表
  - _Requirements: 4.1, 4.3_
  - _Boundary: EmbedderService_

- [x] 2.3 (P) 实现向量相似度搜索服务
  - 实现 `kb/services/searcher.py`：`search(query_vector: list[float], top_k: int = 5) -> list[Chunk]`
  - 使用 `Chunk.objects.select_related('document').order_by(CosineDistance('embedding', query_vector))[:top_k]`
  - 验证：Chunk 表为空时返回 `[]`；有数据时返回 ≤ `top_k` 个结果，且每个 Chunk 已预取 `document` 属性（不触发额外查询）
  - _Requirements: 6.1, 6.2, 7.2_
  - _Boundary: SearcherService_

---

- [ ] 3. Core：视图层与模板
- [x] 3.1 实现 PDF 上传表单与上传视图
  - 实现 `UploadForm`（`kb/forms.py`）：校验上传文件 content_type 为 `application/pdf`、文件大小 > 0 字节、文件大小 ≤ 10MB（10_485_760 字节），否则返回对应中文错误消息
  - 实现 `UploadView.get()`：渲染 `kb/upload.html`（含 `UploadForm`）
  - 实现 `UploadView.post()`：
    - UploadForm 校验失败 → 返回含错误的 `upload.html`
    - 校验通过 → 创建 `Document(status=pending)` → 立即更新 `status=processing` → 进入 `try` 块
    - `try` 块内：`processor.extract_text()` → 若文本为空则 `raise ValueError` → `processor.split_into_chunks()` → `embedder.embed_many()` → 在 `transaction.atomic()` 内执行 `Chunk.objects.bulk_create()` + `Document.chunk_count=N, status=complete` 更新
    - `except` 块：写入 `error_message`，更新 `status=failed`
    - 最终 redirect 到 `/documents/{id}/`（无论成功或失败）
  - 在 `kb/urls.py` 中注册 `path('upload/', UploadView.as_view(), name='upload')`
  - 验证：非 PDF 文件 POST → HTTP 200 响应含表单错误文本；有效 PDF POST → HTTP 302 redirect 到 `/documents/{id}/`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.3_
  - _Depends: 2.1, 2.2_

- [x] 3.2 实现文档详情视图与模板
  - 实现 `DocumentDetailView.get()`：`get_object_or_404(Document, pk=pk)` 获取文档，渲染 `kb/document_detail.html`
  - `kb/templates/kb/document_detail.html`：展示文件名、上传时间；根据 `document.status` 条件渲染：`processing` → "处理中"；`complete` → "处理完成" + chunk_count；`failed` → "处理失败" + error_message；`pending` → "等待处理"
  - 在 `kb/urls.py` 中注册 `path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail')`
  - 验证：访问已处理完成文档的详情页，页面包含文件名、"处理完成"文本和非零的 chunk 数量；访问不存在的 ID 返回 404
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 3.3 实现语义搜索视图、表单与 HTMX 模板
  - 实现 `SearchForm`（`kb/forms.py`）：校验 `query` 字段非空，否则返回错误消息
  - 实现 `SearchView.get()`：渲染 `kb/search.html`（结果区 `<div id="results">` 初始为空）
  - 实现 `SearchView.post()`：
    - HTMX 检测：`is_htmx = request.headers.get("HX-Request") == "true"`
    - SearchForm 校验失败 → 返回表单错误（HTMX 请求返回局部错误模板，普通请求返回完整页面）
    - 校验通过 → `embedder.embed_one(query)` → `searcher.search(vector)` → 渲染
    - HTMX 请求 → 渲染 `kb/partials/search_results.html`；普通请求 → 渲染含结果的 `kb/search.html`
  - `kb/templates/kb/search.html`：包含搜索输入框 + 按钮（设置 `hx-post="{% url 'kb:search' %}"` 和 `hx-target="#results"`）；引用 HTMX CDN
  - `kb/templates/kb/partials/search_results.html`：遍历 chunks 展示每个 Chunk 的 content 和 `chunk.document.filename`；chunks 列表为空时展示"暂无可搜索的文档"
  - 在 `kb/urls.py` 中注册 `path('search/', SearchView.as_view(), name='search')`
  - 验证：带 `HTTP_HX_REQUEST=true` 头的 POST 搜索响应不含 `<html>` 标签，且最多包含 5 个结果项；空查询 POST 响应含校验错误文本
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3_
  - _Depends: 2.2, 2.3_

---

- [ ] 4. 测试
- [x] 4.1 (P) 服务层单元测试
  - `ProcessorService.split_into_chunks`：测试空字符串返回 `[]`；1500 字符返回 2 个块；所有块拼接等于原文本
  - `ProcessorService.extract_text`：使用包含文本的真实 PDF fixture，验证返回非空字符串
  - `EmbedderService.embed_one`：验证返回长度为 384 的 float 列表
  - `EmbedderService.embed_many(['a', 'b', 'c'])`：验证返回长度为 3 的列表
  - `SearcherService.search`：空数据库返回 `[]`；插入带已知向量的 Chunk 后，相同向量查询返回该 Chunk 且包含 `document` 属性
  - 验证：`python manage.py test kb.tests.test_services` 全部通过，无 FAIL 或 ERROR
  - _Requirements: 2.1, 3.1, 4.1_
  - _Boundary: ProcessorService, EmbedderService, SearcherService_

- [x] 4.2 (P) Ingestion 集成测试
  - 上传含文本的真实 PDF fixture → 验证 `Document.status == 'complete'` 且 `Chunk.objects.filter(document=doc).count() > 0`
  - 上传图像型 PDF（无可提取文本）→ 验证 `Document.status == 'failed'` 且 `error_message` 非空字符串
  - Django test client 提交非 PDF 文件 → 验证响应状态码为 200，响应体含表单错误文本
  - Django test client 提交 0 字节文件 → 验证响应状态码为 200，响应体含表单错误文本
  - Django test client 提交超过 10MB 的文件 → 验证响应状态码为 200，响应体含大小限制错误文本
  - 验证：`python manage.py test kb.tests.test_ingestion` 全部通过
  - _Requirements: 1.3, 1.4, 2.1, 2.2, 3.1, 4.1, 4.3_
  - _Boundary: UploadView, ProcessorService, EmbedderService_

- [x] 4.3 (P) 语义搜索端到端集成测试
  - 先 ingestion 含特定关键词的 PDF，再以该关键词搜索 → 验证返回 ≤ 5 个 Chunk，且 Chunk 中包含该关键词
  - 空数据库状态下搜索任意词 → 验证局部模板响应含"暂无可搜索的文档"
  - 带 `HTTP_HX_REQUEST: true` 头 POST `/search/` → 验证响应体不含 `<html>` 标签
  - 空查询 POST `/search/` → 验证响应含校验错误（不调用 EmbedderService 或 SearcherService）
  - 验证：`python manage.py test kb.tests.test_search` 全部通过
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3_
  - _Boundary: SearchView, EmbedderService, SearcherService_

---

- [ ] 5. 基础设施扩展：原始文件存储
- [x] 5.1 配置 MEDIA 与 Document 文件字段
  - 在 `config/settings.py` 配置 `MEDIA_URL` 与 `MEDIA_ROOT`（指向 `BASE_DIR / "media"`，本地文件系统）
  - 在 `config/urls.py` 增加 `from django.conf.urls.static import static` 与 `from django.conf import settings` 导入，并在 `settings.DEBUG` 为真时追加 `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` 配信（开发环境下原文可经链接访问）
  - 为 `Document` 增加可空的原始 PDF 文件字段（`FileField(upload_to='pdfs/', blank=True, null=True)`），生成并应用迁移 `0003_document_file`
  - 验证：`python manage.py migrate` 成功；Django shell 中 `Document` 实例具有 `file` 字段；`DEBUG=True` 下手动放置文件后经 `/media/pdfs/...` 访问返回文件内容
  - _Requirements: 11.1, 11.2_
  - _Boundary: Document, settings, 项目 URL 配置_

- [x] 5.2 (P) 在上传流程中持久化原始 PDF
  - 改写既有 `UploadView.post()` 的读取/保存顺序（修改已完成代码，非纯追加）：将 `file.read()` 提前到创建 Document 之后、ingestion 之前；仅读取一次字节，用 `ContentFile(pdf_bytes)` 保存到 `doc.file`（`save=False`），随后置 `status=processing` 保存，再以同一 `pdf_bytes` 执行既有 `extract_text`
  - 原文保存先于 ingestion：即使后续提取/嵌入抛异常（如图像型 PDF），原始 PDF 仍被保留
  - 验证：上传含文本 PDF 后 `Document.file` 非空且 `doc.file.read()` 等于上传字节；上传图像型 PDF（ingestion 失败）后 `status=='failed'` 但 `Document.file` 仍非空
  - _Requirements: 11.1_
  - _Depends: 5.1_
  - _Boundary: UploadView_

- [x] 5.3 (P) 在文档详情页展示查看原文链接
  - 在 `document_detail.html` 模板中，当 `document.file` 存在时渲染指向 `document.file.url` 的查看链接（`target="_blank"` 新标签页打开）；无原文时不渲染该链接
  - 验证：以直接赋值 `file` 字段构造的（自造 fixture，不依赖 5.2 的上传流程）已存原文文档，其详情页 HTML 含指向原文 URL 的链接；`file` 为空的文档详情页不含该链接
  - _Requirements: 5.5, 11.4_
  - _Depends: 5.1_
  - _Boundary: document_detail.html 模板_

---

- [ ] 6. Core：只读 JSON API
- [x] 6.1 实现文档列表与详情 JSON API
  - 实现序列化助手 `_file_url`（`doc.file` 为真时经 `request.build_absolute_uri(doc.file.url)` 返回绝对 URL，否则 `None`）与 `_document_dict`（id / 文件名 / 状态 / 块数 / 上传时间 ISO / 错误信息 / 原文绝对链接）
  - 实现文档列表端点（`GET /api/documents/`）：返回 `{"documents": [...]}`，空库为空数组；纯 JSON 无 HTML 包装
  - 实现文档详情端点（`GET /api/documents/<int:pk>/`）：有效 ID 返回完整字段；不存在 ID 返回 404 + `{"error": ...}`（JSON）
  - 在应用 URL 配置注册上述两个端点
  - 验证：`GET /api/documents/` 返回 JSON 数组且每项含 `file_url` 字段；`GET` 不存在 ID 返回 404 且响应体为 JSON 错误；响应不含 `<html>`
  - _Requirements: 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 11.3, 11.4_
  - _Depends: 5.1_
  - _Boundary: api_views, 应用 URL 配置_

- [x] 6.2 实现语义搜索 JSON API
  - 实现 `_chunk_dict` 序列化助手：将 Chunk 转为含内容 / 所属文档名 / 文档 ID / 原文绝对链接的字典（复用 searcher 已预取的 `chunk.document`，不触发额外查询）
  - 实现搜索端点（`POST /api/search/`，`Content-Type: application/json`，body 为 `{"query": ...}`）：解析 JSON body 并复用既有 `SearchForm` 查询校验，空/缺失/非法 JSON → 400 + `{"error": ...}` 且不调用 embedder/searcher；有效查询经 `embed_one` + `search(top_k=5)` 返回 `{"results": [...]}`
  - 对搜索端点豁免 CSRF（`csrf_exempt`，服务端到服务端调用）；Chunk 表为空时返回 `results` 为空列表而非错误
  - 在应用 URL 配置注册该端点
  - 验证：以 JSON body 提交关键词 `POST /api/search/` 返回 ≤5 个含 `file_url` 的结果；空查询返回 400 JSON 且不触发嵌入；空库返回 `results` 为空列表；响应不含 `<html>`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 11.4_
  - _Depends: 5.1, 6.1_
  - _Boundary: api_views, 应用 URL 配置_

---

- [ ] 7. 测试：文件存储与 JSON API
- [x] 7.1 (P) 原始文件存储与详情链接测试
  - 上传含文本 PDF → `Document.file` 非空且字节匹配上传内容；上传图像型 PDF → `status=='failed'` 但 `Document.file` 仍非空
  - 以自造 `file` fixture 的文档 → 详情页 HTML 含查看原文链接；无 `file` 的文档 → 详情页不含该链接
  - 验证：`python manage.py test knowledge_base.tests.test_file_storage` 全部通过
  - _Requirements: 5.5, 11.1, 11.2_
  - _Depends: 5.2, 5.3_
  - _Boundary: UploadView, document_detail.html_

- [x] 7.2 (P) JSON API 测试
  - 列表 API：有 / 无文档分别返回非空数组 / 空数组，每项含 `file_url`
  - 详情 API：有效 ID 返回完整字段 + `file_url`；不存在 ID 返回 404 JSON
  - 搜索 API：JSON body 关键词 → ≤5 结果含 `file_url`；空查询 → 400 且不调用 embedder/searcher；空库 → `results` 空列表；响应不含 `<html>`
  - `file_url` 空值：`file` 为空的文档其 JSON 中 `file_url` 为 `null`
  - 验证：`python manage.py test knowledge_base.tests.test_api` 全部通过
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 11.3, 11.4_
  - _Depends: 6.1, 6.2_
  - _Boundary: api_views_
