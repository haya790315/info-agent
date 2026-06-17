# PDF 知识库 — 本地 RAG 学习项目

基于 Django + HTMX + pgvector 构建的 RAG（检索增强生成）检索层学习项目。
上传 PDF 后自动提取文本、分块、生成向量嵌入，支持自然语言语义搜索。

---

## 环境要求

| 依赖         | 说明                                                                                   |
| ------------ | -------------------------------------------------------------------------------------- |
| Python 3.10+ | 运行 Django 应用                                                                       |
| uv           | Python 包管理器（[安装说明](https://docs.astral.sh/uv/getting-started/installation/)） |
| Docker       | 运行 PostgreSQL + pgvector（无需本地安装数据库）                                       |

---

## 启动步骤

### 1. 安装 Python 依赖

```bash
make install
```

> 首次安装时 `sentence-transformers` 会下载约 90MB 的模型文件。

### 2. 启动数据库（Docker）

```bash
make db
```

自动完成：启动 PostgreSQL 容器 → 等待就绪 → 启用 `vector` 扩展。

### 3. 执行数据库迁移

```bash
make migrate
```

### 4. 启动开发服务器

```bash
make dev
```

用浏览器打开 http://127.0.0.1:8000/upload/

---

## 使用说明

### 上传 PDF

1. 打开 http://127.0.0.1:8000/upload/
2. 点击「选择文件」选择 PDF（最大 10MB）
3. 点击「上传」按钮
4. 处理完成后自动跳转到文档详情页

> 仅支持包含文本的 PDF。纯图片型 PDF 会显示「处理失败」。

### 查看文档状态

上传后的详情页（`/documents/{id}/`）会显示当前状态：

| 状态     | 说明               |
| -------- | ------------------ |
| 等待处理 | 排队等待中         |
| 处理中   | 正在提取/嵌入      |
| 处理完成 | 成功，显示分块数量 |
| 处理失败 | 失败，显示错误原因 |

### 语义搜索

1. 打开 http://127.0.0.1:8000/search/
2. 在搜索框中输入问题或关键词
3. 点击「搜索」按钮
4. 页面无刷新（HTMX）展示最多 5 条语义相关的文本块，每条显示所属文件名

---

## 其他命令

| 命令            | 说明                                          |
| --------------- | --------------------------------------------- |
| `make db-stop`  | 停止数据库容器                                |
| `make db-reset` | 清空数据库（删除容器 + 数据卷，数据不可恢复） |
| `make db-logs`  | 查看数据库日志                                |
| `make test`     | 运行测试（无需 Docker）                       |

---

## 运行测试

```bash
make test
```

> 测试使用 SQLite 内存数据库，无需启动 Docker。

---

## 项目结构

```
docker-compose.yml  # PostgreSQL + pgvector 容器配置
rag_agent/          # Django 项目配置
kb/
  models.py         # Document、Chunk 数据模型
  views.py          # UploadView、DocumentDetailView、SearchView
  forms.py          # UploadForm、SearchForm
  urls.py           # URL 路由
  services/
    processor.py    # PDF 文本提取与分块
    embedder.py     # 向量嵌入（all-MiniLM-L6-v2，384 维）
    searcher.py     # pgvector 余弦相似度搜索
  templates/kb/
    base.html             # 公共布局（含 HTMX CDN）
    upload.html           # 上传页
    document_detail.html  # 文档详情页
    search.html           # 搜索页
    partials/
      search_results.html # HTMX 搜索结果局部模板
```
