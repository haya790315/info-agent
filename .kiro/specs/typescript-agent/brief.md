# Brief: typescript-agent

## Problem

企业内部员工（HR、法务、业务等非工程师）需要查询规章、契约范本、产品说明等内部 PDF 文件时，目前只能逐页翻找或用 Ctrl+F 做完全比对的关键字搜索，找不到同义表达，效率低下。员工往往「知道资讯在某份 PDF 里，但找不到在哪一页」。

## Current State

既有 Django + pgvector 后端已完成 PDF ingestion 与语义搜索能力（`knowledge_base/services/`：processor / embedder / searcher，含测试）。但仅有 HTML 模板视图，使用者必须手动输入关键字、自行阅读搜索结果片段；没有自然语言对话层，也没有 JSON API 可供外部程序调用。

## Desired Outcome

使用者在网页聊天框用自然语言提问（例如「试用期满后年休假怎么算？」），Agent 自主判断并调用知识库工具、彙整出带来源（文件名 + 片段）的自然语言回答；同一套工具同时以 MCP Server 形式暴露，可被其他 MCP 客户端复用。

## Approach

TypeScript + Bun runtime，Hono 作为轻量 Web framework。自行实现 Agent Loop：接收问题 → 带 tool 定义送 LLM → LLM 决定调用工具 → 执行工具（HTTP fetch 调用 Django REST API）→ 结果回 LLM → 生成最终回答。三个工具（`search_knowledge_base` / `list_documents` / `get_document_detail`）封装对 Django REST API 的调用。同一套工具逻辑再包装为 MCP Server。Web UI 为纯 HTML（无 build 步骤）。Tool Use 过程打印到 console 便于观察思考过程。

## Scope

- **In**:
  - Agent Loop（LLM Function Calling，自行实现循环，非框架黑盒）。
  - 三个 Tool 的定义与执行逻辑（调用 Django REST API）。
  - Hono Web Server：提供 HTML 页面 + `POST /api/chat` endpoint。
  - 纯 HTML 聊天 UI（输入问题、显示回答）。
  - 思考过程 console log。
  - MCP Server（同一套 tools 包装为 MCP）。
- **Out**:
  - Django 侧的 REST API 实现（属 pdf-knowledge-base spec 的 Task 5）。
  - embedding 与向量搜索逻辑（保留在 Python 侧）。
  - 用户认证、对话历史持久化（首版可为无状态或仅内存内多轮）。

## Boundary Candidates

- Agent Loop（LLM 编排核心 `agent.ts`）
- Tool 定义与执行（`tools.ts`，调用 Django REST API）
- Web 层（Hono server + HTML UI，`index.ts` + `public/index.html`）
- MCP Server（`mcp-server.ts`，复用 tools.ts 的工具逻辑）

## Out of Boundary

- Django REST API 端点本身（依赖项，由 pdf-knowledge-base 提供）。
- PDF 上传 / ingestion 流程。
- 嵌入模型与 pgvector 搜索。

## Upstream / Downstream

- **Upstream**: pdf-knowledge-base 的 REST API（`POST /api/search/`、`GET /api/documents/`、`GET /api/documents/<id>/`）—— 必须先定稿其 JSON 契约。
- **Downstream**: MCP Server 暴露后，可被其他 MCP 客户端（如 Claude Desktop 等）作为知识库工具复用。

## Existing Spec Touchpoints

- **Extends**: 无（全新 spec）。
- **Adjacent**: pdf-knowledge-base —— 仅通过 REST API 的 JSON 契约耦合；TS 侧 Tool 的请求/响应结构必须严格对齐 Django 侧定义。

## Constraints

- **TypeScript + Bun**：必要要件，标准 runtime，启动快、无 build 步骤。
- **Hono**：与 Bun 相性最佳的轻量 Web framework。
- **LLM 供应商**：企划书写「OpenAI API，免费 tier 每日 1500 次、无需信用卡」，但该免费额度描述更接近 Google Gemini。设计阶段需确认实际供应商；只要走 OpenAI 兼容的 Function Calling 协议，Agent Loop 实现即可保持一致。
- **纯 HTML UI**：无前端 build 工具链。
- **依赖顺序**：本 spec 的 Tool 实现依赖 Django REST API 契约，需待 pdf-knowledge-base Task 5 的端点契约确定后对齐。
