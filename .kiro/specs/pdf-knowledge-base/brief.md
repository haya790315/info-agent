# Brief: pdf-knowledge-base

## 问题背景
学习 RAG 系统基础的开发者，希望在不引入 LLM 的前提下，仅实现检索（Retrieval）部分，通过动手体验分块、嵌入、向量搜索的工作原理。

## 现状
代码库为空。`inital.md` 中已定义需求、技术栈和数据流。

## 目标结果
- 上传 PDF 后，能完成文本提取、分块、嵌入生成、向量数据库存储
- 用自然语言查询，能对 PDF 内容进行语义搜索
- 返回最相关的前 5 个文本块并在页面展示

## 架构方案

**服务层架构（方案B）**

单一 Django 应用 `kb`，pipeline 各步骤拆分为独立 service 模块：

| 模块 | 职责 |
|------|------|
| `processor.py` | PyMuPDF 文本提取 + 固定大小分块 |
| `embedder.py` | sentence-transformers 生成嵌入向量 |
| `searcher.py` | pgvector 余弦相似度搜索 |

前端使用 HTMX 实现无刷新交互。

## 范围

**包含：**
- PDF 上传（单文件）
- 文本提取（PyMuPDF）
- 固定大小分块（chunk_size=1000）
- 嵌入生成（all-MiniLM-L6-v2）
- 向量存储（PostgreSQL + pgvector）
- 语义搜索（返回前 5 个结果）
- 三个页面：上传页 / 文档详情页 / 搜索页

**不包含：**
- LLM、聊天界面、Agent
- 用户认证、多用户支持
- 异步任务队列（Celery 等）
- GitHub 集成、代码审查功能

## 责任边界

- **文档摄取**：upload → extract → chunk → embed → store（单次同步流程）
- **语义搜索**：query embed → pgvector search → 结果展示
- **数据模型**：Document / Chunk（含 VectorField）

## 边界之外

- LLM 生成答案（Phase 2 之后）
- 多文档高级排序
- 非 PDF 来源（URL、代码仓库）

## 上下游依赖

- **上游**：无（绿地项目）
- **下游**：
  - Phase 2：LLM 集成（只需新增 `llm.py`）
  - Phase 3：多文档知识库
  - Phase 4：源码文件检索
  - Phase 5：AI 代码审查平台

## 约束条件

- 仅本地运行，不使用云端 API
- sentence-transformers 本地推理，无需付费 API
- 必须使用 PostgreSQL + pgvector
- 前端限 Django + HTMX，不使用 SPA 框架
- 同步处理（上传时阻塞执行，不引入异步队列）
