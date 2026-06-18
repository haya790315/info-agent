# 差距分析：typescript-agent

> 2026-06-18。本规格为**全新 TypeScript 服务**（repo 内无任何 TS/Bun 代码），作为既有 Django 知识库 REST API 的消费方与编排层。下方分析基于代码库实况 + 外部技术栈实测调研。

## 1. 现状调查

### 既有资产（可复用 / 依赖）

| 资产 | 位置 | 对本规格的意义 |
|------|------|----------------|
| 知识库 REST API（3 端点） | `knowledge_base/api_views.py` + `urls.py` | **上游依赖（已完成并验证）**。本服务全部检索经此访问 |
| `POST /api/search/` | body `{"query": str}` → `{"results": [{content, filename, document_id, file_url}]}`；空查询 400 `{"error"}`；空库 `{"results": []}` | 语义搜索工具的后端 |
| `GET /api/documents/` | → `{"documents": [{id, filename, status, chunk_count, uploaded_at, error_message, file_url}]}` | 文档列表工具的后端 |
| `GET /api/documents/<id>/` | → 单个 document dict；不存在 404 `{"error"}` | 文档详情工具的后端 |
| `file_url` 字段 | 绝对 URL（`build_absolute_uri`），未存原文为 `null` | 回答中"原文链接"的来源 |

### TypeScript 侧现状
- **完全绿地**：无 `package.json` / `tsconfig.json` / `*.ts` / `agent/` 目录。一切从零搭建。

## 2. 需求 → 资产映射（差距标签：缺失 / 未知 / 约束）

| 需求 | 所需能力 | 标签 |
|------|----------|------|
| 1 自然语言问答 | chat 端点 + Agent 编排 + 回答拼装（含来源/链接） | 🔴 缺失 |
| 2 会话内多轮 | 内存内会话存储 + 历史随请求传入 LLM + 会话隔离 | 🔴 缺失 |
| 3 Agent 循环 | tool-call 调度循环 + 轮次上限 | 🔴 缺失 |
| 4/5/6 三工具 | 工具注册表，各自 `fetch` 调 Django REST API | 🔴 缺失（后端 ✅ 已存在） |
| 7 思考日志 | 循环内 console 输出工具名/参数/结果摘要 | 🔴 缺失 |
| 8 Web UI | Hono server + 静态 HTML 聊天页 | 🔴 缺失 |
| 9 MCP Server | MCP 适配器复用同一套工具 | 🔴 缺失 |
| 10 错误处理 | LLM 失败 / 上游 API 失败 / 空结果不编造 | 🔴 缺失 |
| 11 上游依赖 | 全部经 REST API，契约对齐 | ⚠️ 约束（契约已定稿） |

## 3. 实现途径

绿地服务，**无既有 TS 可扩展（Option A 不适用）**，唯一可行是 **Option B：全新模块化服务**。真正的决策点在「采用何种库」与「几个关键技术选择」。

### 推荐技术栈（已实测版本，2026-06-18）

| 组件 | 选型 | 版本 / 备注 |
|------|------|------------|
| Runtime | Bun | 1.3.x（许可 MIT） |
| Web 框架 | Hono + `hono/bun` `serveStatic` | 4.12.26（MIT）；环境变量走 `process.env`（Bun 上 `c.env` 拿不到） |
| LLM SDK | `openai`（Chat Completions API） | 6.44.0（Apache-2.0）；**不要用 Responses API**（Gemini 不兼容） |
| LLM 提供商（默认） | **Gemini Flash 免费层 OpenAI 兼容端点** | `baseURL: .../v1beta/openai/`，免信用卡 |
| MCP | `@modelcontextprotocol/sdk`（**stdio 优先**） | 1.29.0（MIT） |
| MCP-on-HTTP（可选） | `@hono/mcp` | 0.3.0（MIT） |
| 工具参数 schema | zod（Agent 与 MCP 双端共享） | 单一定义源，避免漂移 |

### 关键决策 A：LLM 提供商（须 design 拍板）

> **重要更正**：brief 写「OpenAI free tier 每日 1500 次、无需信用卡」**是错误描述**——该额度精确匹配 **Google Gemini**，OpenAI 并无此免费层（一次性试用额度已于 2025 停发，且注册需信用卡）。

| 选项 | 说明 | 取舍 |
|------|------|------|
| **Gemini Flash 免费层（推荐）** | OpenAI 兼容端点，免信用卡，~1500 RPD | ✅ 真正满足 brief 的"免费"意图 ❌ JSON Schema 仅支持子集（工具 schema 要保守，否则 400）；额度按 GCP Project 计、可能用于训练 |
| OpenAI 付费 | 需信用卡、按量计费 | ✅ Schema 支持完整 ❌ 不符合"免费"约束 |
| 抽象 `LLMClient` 层 | 配置化 baseURL/model/key，两者皆可切 | ✅ 隔离差异、可移植 ❌ 略增抽象成本（推荐采纳，成本低收益高） |

### 关键决策 B：MCP transport（须 design 拍板）

| 选项 | 取舍 |
|------|------|
| **stdio（推荐）** | ✅ 最简稳定，client 把 server 当子进程拉起 ❌ 仅本地 |
| Streamable HTTP（`@hono/mcp`） | ✅ 可远程、可挂 Hono 路由 ❌ **Bun 下 SSE/HTTP transport 启动慢（实测有 ~15s 报告，bun#22396）**，需实测 |

### 单一工具定义源（强烈推荐的结构）

每个工具实现为纯函数 `{ name, description, parameters(zod), execute(args) }`，集中于一个工具注册表模块（各自 `fetch` 调 Django API）。Agent Loop 与 MCP Server 各写 ~10 行薄适配器消费它：
- **Agent 适配器**：注册表 → OpenAI `tools` 数组；收到 `tool_calls` 按 name 调 `execute`，结果作 `role:'tool'` 消息回灌
- **MCP 适配器**：注册表 → `server.registerTool(name, {description, inputSchema}, execute)`
- zod schema 既生成 OpenAI JSON Schema 又作 MCP `inputSchema`，**业务逻辑零分叉**（直接满足需求 9.3「MCP 与 Agent 结果一致」）

## 4. 工数与风险

| 项目 | 工数 | 风险 | 根据 |
|------|------|------|------|
| 工具注册表（3 工具 + fetch 调 API） | S | Low | 契约已定稿，纯 HTTP 调用 + JSON 映射 |
| Agent Loop（Function Calling + 轮次上限 + 多轮历史） | M | Medium | 自行实现循环，需处理 tool_calls 往返、会话状态、上限 |
| Hono server + 静态 HTML 聊天 UI | S | Low | 标准模式 |
| MCP Server 适配器 | S | Low-Medium | SDK 成熟；transport 选择有 Bun 启动延迟坑 |
| 错误处理与降级 | S | Low | LLM/上游失败/空结果分支 |
| 项目脚手架（package.json/tsconfig/Bun 配置） | S | Low | 必须显式建（绿地） |

**总体：M / Medium**。无致命阻断项；风险集中在「repo 内首个 TS/Bun 栈」+ Gemini schema 子集 + 免费层额度。

## 5. 设计阶段须解决（Research Needed）

1. **LLM 提供商终选**：Gemini 免费层（默认）vs OpenAI vs 双支持抽象层；确认 model 名与 baseURL
2. **chat 端点是否流式输出（SSE）**：若是，实测 Bun fetch 流式内存泄漏（bun#18488）
3. **MCP transport 终选**：stdio（推荐）vs HTTP；HTTP 须实测 Bun 启动延迟
4. **Gemini 工具 schema 兼容性**：用实际 3 工具 schema 跑一次确认无 400（JSON Schema 子集限制）
5. **免费层额度是否够用**：1500 RPD / 10–15 RPM 对「单轮可能多次 tool-call 往返」的 Agent Loop 可能偏紧，需评估
6. **会话标识与生命周期**：内存内多轮的 session 如何标识（session id / 连接）、何时过期、内存上限
7. **Django API 的 CORS/可达性**：TS 服务（Bun）→ Django 为服务端到服务端调用，确认 Django base URL 配置化（环境变量）；文件链接为浏览器直接导航，无需 CORS（已在 pdf-knowledge-base 设计中确认）

## 6. 推荐

- **途径**：Option B（全新模块化服务）+ 单一工具定义源结构
- **栈**：Bun 1.3 / Hono 4.12 / `openai` v6（Chat Completions）/ **默认 Gemini Flash 免费层 OpenAI 兼容端点** / MCP SDK 1.29（stdio）/ zod 双端共享
- **优先级**：先工具注册表（契约已就绪）→ Agent Loop → Web UI → MCP 适配器 → 错误处理
- **务必在 design 处理**：把 brief 的「OpenAI 免费层」更正为 Gemini（或抽象 `LLMClient`），否则实现期会撞上"无免费额度"的现实
- **许可证**：全部宽松（MIT / Apache-2.0），无障碍

---

# 设计合成（design 阶段）

> 2026-06-18。用户决策：**LLM 供应商确定使用 OpenAI**（覆盖本 gap 分析的「Gemini 免费层默认」建议）。

## Build vs Adopt（确认）
- **采用** `openai` v6（Chat Completions API，**非 Responses API**）做 Function Calling
- **采用** Hono 4.12 + `hono/bun`（静态配信 + chat 端点）
- **采用** `@modelcontextprotocol/sdk` 1.29，**stdio transport**（首版；规避 Bun HTTP 启动延迟）
- **采用** zod 作为工具参数 schema 的单一来源（生成 OpenAI JSON Schema 与 MCP inputSchema）

## 供应商决策的影响（OpenAI）
- **不再采用 Gemini 免费层**。OpenAI 无免信用卡免费层 → 需自备**付费 API key**；gap 分析中「免费额度是否够用」一项**不再适用**，改为关注调用成本
- **不需要供应商抽象层**：既已锁定 OpenAI，`LLMClient` 仅做 `openai` SDK 薄封装；key/model/baseURL 经 env 配置（`OPENAI_API_KEY` / `OPENAI_MODEL` / 可选 `OPENAI_BASE_URL`），保留切换余地但不引入多供应商分支逻辑
- **Gemini JSON Schema 子集限制不再是约束**（OpenAI 支持完整 Function Calling schema）；工具 schema 仍保持简洁

## 简化（Simplification）
- **单一工具定义源**：3 工具的 `execute` 只写一次，Agent 适配器与 MCP 适配器各 ~10 行格式转换 → 直接满足需求 9.3「MCP 与 Agent 结果一致」，无需额外一致性校验逻辑
- **camelCase 映射收敛在 KbClient 边界**：Django 的 snake_case（`document_id`/`file_url`）只在 KbClient 转换一次，其余层用统一 DTO
- **无持久化**：会话仅内存内 Map，无数据库/无 schema 迁移

## 剩余 Open Questions（实现期/后续）
- 流式输出（SSE）— 首版非流式
- MCP transport stdio→HTTP 切换的 Bun 启动延迟
- 会话内存上限 / TTL 参数
- OpenAI 调用成本（Agent Loop 多轮 tool-call token 叠加）
