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
