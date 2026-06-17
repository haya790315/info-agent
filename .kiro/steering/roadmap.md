# Roadmap

## Overview

为既有的 PDF 知识库（Django + pgvector 语义搜索）加上一层「自然语言 AI Agent」交互能力。使用者用自然语言提问，Agent 通过 LLM Function Calling 自主决定调用哪个工具（语义搜索 / 文档列表 / 文档详情），从知识库检索后彙整出带来源的回答，免去手动关键字搜索。

整体分两条工作流：先在既有 Django 后端补上 JSON REST API（供 Agent 调用），再新建独立的 TypeScript（Bun + Hono）Agent 服务实现 Agent Loop、Web 聊天 UI 与 MCP Server。

## Approach Decision

- **Chosen**: 双层架构 —— Django 仅暴露无状态 REST API（embedding + pgvector 搜索保留在 Python 侧），TypeScript/Bun 侧负责 Agent Loop、工具编排、Web UI 与 MCP Server。
- **Why**:
  - 不重复造轮子：既有的 `all-MiniLM-L6-v2` 嵌入模型与 pgvector 搜索逻辑（`knowledge_base/services/`）已完成且测试覆盖，直接复用。
  - 职责清晰：Python 负责「检索」，TypeScript 负责「智能编排与对话」，两层通过 HTTP 解耦，可独立开发与测试。
  - 符合要件：TypeScript + Bun 为必要要件；Agent Loop / Tool Use / Web UI / MCP 均落在 TS 侧。
- **Rejected alternatives**:
  - 全部用 Python（Django + LangChain）实现 Agent：不满足 TypeScript 必要要件。
  - 在 TS 侧重新实现 embedding 与向量搜索：重复造轮子，且需要在 Node/Bun 生态重新加载模型，违背复用原则。

## Scope

- **In**:
  - Django 侧新增三个 JSON REST 端点（search / documents list / document detail）。
  - TypeScript/Bun Agent 服务：Agent Loop（LLM Function Calling）、三个 Tool、Hono Web Server、纯 HTML 聊天 UI、思考过程 console log、MCP Server。
- **Out**:
  - 既有 PDF 上传 / ingestion 流程的改动（已完成，保持不变）。
  - 用户认证 / 权限管理 / 多租户。
  - 对话历史持久化（首版为无状态单轮或内存内多轮）。

## Constraints

- **TypeScript + Bun** 为必要要件（标准 runtime）。
- LLM 供应商：企划书写「OpenAI API，免费 tier 每日 1500 次、无需信用卡」。注意：该免费额度描述实际更接近 Google Gemini 而非 OpenAI（OpenAI 无此免费 tier）。**需在 typescript-agent spec 阶段确认实际 LLM 供应商**——只要支持 Function Calling（OpenAI 兼容协议）即可，Agent Loop 实现不受影响。
- REST API 复用既有 Django service 层，**不引入 Django REST Framework**，用内置 `JsonResponse` 即可。
- Web UI 为纯 HTML（无 build 步骤）。

## Boundary Strategy

- **Why this split**: 「检索能力」与「Agent 编排」是两个天然责任缝。前者是既有 Python 资产的薄 API 封装，后者是全新的 TypeScript 工作流。分开后 Django 侧改动极小（可作为既有 spec 的 Task 5 扩展），TS 侧可作为独立 spec 全新开发。
- **Shared seams to watch**: REST API 的请求/响应 JSON 契约（字段名、结构）是两层之间的唯一接口，必须在 Django 侧定稿后，TS 侧的 Tool 实现严格对齐。建议在 typescript-agent 设计阶段明确记录该契约。

## Existing Spec Updates

- [ ] pdf-knowledge-base — 新增 Task 5：三个只读 JSON REST 端点（`POST /api/search/`、`GET /api/documents/`、`GET /api/documents/<id>/`），复用既有 `services/embedder.py`、`services/searcher.py` 与 `Document` 模型。Dependencies: none（既有 service 层已完成）

## Direct Implementation Candidates

（无——所有工作均落入上述 spec 更新或新 spec）

## Specs (dependency order)

- [ ] typescript-agent — Bun + Hono Agent 服务：Agent Loop（LLM Function Calling）+ 3 个 Tool + 纯 HTML 聊天 UI + 思考过程 log + MCP Server。Dependencies: pdf-knowledge-base（依赖其 REST API 契约）
