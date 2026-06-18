# 实现计划

- [ ] 1. 基础设施：项目骨架与配置
- [x] 1.1 创建 Bun + TypeScript 项目骨架与配置加载
  - 在 `agent/` 创建 `package.json`（依赖：`hono`、`openai`、`@modelcontextprotocol/sdk`、`zod`；脚本 `dev`/`test`）与 `tsconfig.json`（strict、禁用隐式 any）
  - 创建 `.env.example`：`OPENAI_API_KEY`、`OPENAI_MODEL`、可选 `OPENAI_BASE_URL`、`KB_API_BASE_URL`
  - 实现 `src/config.ts`：启动时加载并校验必填环境变量，缺失时以明确错误退出
  - 验证：`bun install` 成功；`bunx tsc --noEmit` 无类型错误；缺失必填 env 时 config 加载抛出明确错误
  - _Requirements: 11.1_

- [x] 1.2 定义共享类型
  - 实现 `src/types.ts`：`ChatMessage`（system/user/assistant/tool 判别联合）、`ToolCall`、`AssistantTurn`、`LLMToolSpec`、KB DTO（`SearchResultItem`/`DocumentSummary`/`DocumentDetail`）、`ToolResult`（ok 判别联合）、`ToolDefinition`
  - 验证：`bunx tsc --noEmit` 通过；类型中不出现 `any`（以 `unknown` 或精确类型替代）
  - _Requirements: 11.2_

---

- [ ] 2. Core：基础组件（三者可并行）
- [x] 2.1 (P) 实现 KbClient（知识库 REST API 客户端）
  - 实现 `src/tools/kbClient.ts`：`search(query)`→`POST /api/search/`；`listDocuments()`→`GET /api/documents/`；`getDocument(id)`→`GET /api/documents/<id>/`
  - 将 Django snake_case JSON 映射为 camelCase DTO（`document_id`→`documentId`、`file_url`→`fileUrl`）；base URL 取自 `KB_API_BASE_URL`
  - 错误处理：`search` 空结果→`[]`；`listDocuments` 空库→`[]`；`getDocument` 对 404→`null`；上游不可达/非 2xx（非 404）→抛 `KbApiError`
  - 验证：mock fetch 返回 Django `{results:[...]}` → 返回映射后 camelCase DTO；404 响应 → `getDocument` 返回 `null`；非 2xx → 抛 `KbApiError`
  - _Requirements: 4.1, 4.2, 5.1, 5.2, 6.1, 11.1, 11.2_
  - _Boundary: KbClient_
  - _Depends: 1.1, 1.2_

- [x] 2.2 (P) 实现 SessionStore（内存内会话历史）
  - 实现 `src/session.ts`：`getHistory(sessionId)`（不存在返回 `[]`）、`append(sessionId, ...messages)`；内部 `Map<string, ChatMessage[]>`
  - 仅内存保存，无持久化（重启即失）；不同 sessionId 互相隔离
  - 验证：append 后 getHistory 顺序正确；两个不同 sessionId 历史互不干扰；不存在的 sessionId 返回 `[]`
  - _Requirements: 2.3, 2.4_
  - _Boundary: SessionStore_
  - _Depends: 1.2_

- [x] 2.3 (P) 实现 LLMClient（OpenAI Chat Completions 封装）
  - 实现 `src/llm.ts`：`chat(messages, tools)` 经 `openai` SDK 调用 **Chat Completions API**（非 Responses API），返回 `AssistantTurn`（content 与 toolCalls）
  - key/model/baseURL 取自 config；无状态（历史由调用方传入）；调用失败/超时 → 抛 `LLMError`
  - 验证：注入 mock OpenAI client，`chat` 正确传递 messages 与 tools 并解析出 `toolCalls`/`content`；底层抛错时 `chat` 抛 `LLMError`
  - _Requirements: 3.1, 2.2, 10.1_
  - _Boundary: LLMClient_
  - _Depends: 1.1, 1.2_

---

- [ ] 3. Core：工具注册表与 Agent 编排
- [x] 3.1 实现 ToolRegistry（单一工具定义源）
  - 实现 `src/tools/registry.ts`：三工具 `{name, description, parameters(zod), execute}` —— `search_knowledge_base({query})`、`list_documents({})`、`get_document_detail({document_id})`，各自经 KbClient 调用
  - `execute` 是工具业务逻辑唯一所在；`search` 空结果→`{ok:true,data:[]}`；`get_document_detail` 对不存在→`{ok:false,error:"文档不存在"}`；`KbApiError`→`{ok:false,error}`
  - 验证：`search_knowledge_base.execute` 空结果返回 `{ok:true,data:[]}`；`get_document_detail` 对不存在 ID 返回 `{ok:false}`；KbClient 抛错时返回 `{ok:false}`
  - _Requirements: 4.1, 4.3, 5.1, 6.1, 6.2, 9.3, 10.2_
  - _Depends: 2.1_

- [x] 3.2 实现 AgentLoop（Function Calling 循环）
  - 实现 `src/agent.ts`：`run(sessionId, userMessage)` —— 取会话历史 → 以 `[system]+history+[user]` 循环 `LLMClient.chat`；有 `toolCalls` 则按 name 调 `ToolRegistry.execute`、以 `role:"tool"` 回灌；无则为最终回答
  - 轮次上限 `MAX_TOOL_ROUNDS`：达上限时**再做一次禁用工具的 LLM 调用**强制出文字答案；仍无内容则返回固定降级文案（绝不返回空回答）
  - 系统提示词约束：借助工具检索、引用来源、空结果不编造；**确定性拼接来源区块**——收集本轮实际 `search_knowledge_base` 返回的文件名+`fileUrl`（去重）追加到回答末尾
  - 每次工具调用前后向 console 输出工具名/参数/结果摘要；最终将本轮 user+assistant 写回 SessionStore
  - 验证：mock LLM 先返回 tool_calls 再返回最终回答 → 执行了对应工具且回答末尾含来源区块（文件名+fileUrl）；无 tool_calls 时不调用工具直接返回；达轮次上限时返回非空文字答案
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 3.5, 7.1, 7.2, 10.1, 10.3_
  - _Depends: 3.1, 2.2, 2.3_

---

- [ ] 4. Integration：Web 层
- [x] 4.1 实现 Hono WebServer 与 chat 端点
  - 实现 `src/index.ts`：Hono server，`GET /` 与 `/public/*` 经 `serveStatic` 提供静态页；`POST /api/chat` 接收 `{sessionId?, message}` → 调 `AgentLoop.run` → 返回 `{answer, sessionId}`
  - `message` 为空或仅空白 → `400 {error}` 且不调用 AgentLoop；无 `sessionId` 时服务端生成并在响应返回
  - 验证：空 message POST → 400 且响应含 error；正常 message POST → 200 含 answer 与 sessionId（注入 mock AgentLoop）
  - _Requirements: 1.1, 1.4, 8.1_
  - _Depends: 3.2_

- [x] 4.2 实现纯 HTML 聊天 UI
  - 实现 `agent/public/index.html`：原生 `fetch` 提交问题至 `POST /api/chat`，将回答追加至对话区；保存服务端返回的 `sessionId` 用于后续请求（维持多轮）
  - 按顺序展示当前会话问答记录；fetch 期间显示「处理中」状态指示
  - 验证：浏览器打开页面，提交问题后对话区出现问答；连续提问复用同一 sessionId；请求期间可见处理中提示
  - _Requirements: 1.5, 8.2, 8.3_
  - _Depends: 4.1_

---

- [ ] 5. Integration：MCP Server
- [x] 5.1 (P) 实现 MCP Server（stdio，复用同一工具注册表）
  - 实现 `src/mcp-server.ts`：遍历 `ToolRegistry`，对每个工具 `server.registerTool(name, {description, inputSchema}, 包装(execute))`；inputSchema 由工具 zod schema 转换
  - handler 调用**同一** `execute`，结果包装为 MCP `content:[{type:"text", text: JSON.stringify(...)}]`；transport 用 stdio
  - 验证：启动 MCP server 后，列出工具含三者；调用某工具返回结构化 content；同输入下结果与直接调用 registry.execute 一致
  - _Requirements: 9.1, 9.2, 9.3_
  - _Boundary: MCPServer_
  - _Depends: 3.1_

---

- [ ] 6. 测试
- [x] 6.1 (P) 基础组件单元测试
  - KbClient：mock fetch → search 映射 camelCase、空结果 `[]`；getDocument 404→`null`、非 2xx→`KbApiError`
  - ToolRegistry：search 空→`{ok:true,data:[]}`；get_document_detail 不存在→`{ok:false}`；KbApiError→`{ok:false}`
  - SessionStore：会话隔离、append/getHistory 顺序
  - 测试文件独立（如 `src/tools/kbClient.test.ts`/`registry.test.ts`/`session.test.ts`），与 6.2/6.3 不共享文件
  - 验证：`bun test` 相关用例全部通过
  - _Requirements: 4.1, 4.3, 5.1, 5.2, 6.1, 6.2, 2.3, 2.4, 10.2, 11.2_
  - _Boundary: KbClient, ToolRegistry, SessionStore_
  - _Depends: 2.1, 2.2, 3.1_

- [x] 6.2 (P) AgentLoop 集成测试
  - 工具往返：mock LLM 返回 tool_calls→最终回答 → 执行工具、回答末尾含确定性来源区块（文件名+fileUrl）
  - 轮次上限：mock LLM 持续返回 tool_calls → 达 `MAX_TOOL_ROUNDS` 后禁用工具收尾，返回**非空**答案
  - 无工具路径：mock LLM 直接返回最终回答 → 不调用工具
  - 多轮：同一 sessionId 两次 run → 第二次 chat 的 messages 含首轮历史
  - LLM 失败：mock LLM 抛 `LLMError` → 返回友好错误而非崩溃/空
  - 测试文件独立（如 `src/agent.test.ts`），与 6.1/6.3 不共享文件
  - 验证：`bun test` 相关用例全部通过
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.2, 3.3, 3.4, 3.5, 7.1, 7.2, 10.1, 10.3_
  - _Boundary: AgentLoop_
  - _Depends: 3.2_

- [x] 6.3 (P) Web 端点与 MCP 一致性测试
  - chat 端点：空 message→400；正常 message→200 含 answer 与 sessionId（mock AgentLoop）
  - MCP 一致性：经 MCP 适配器调用某工具与直接 `registry.execute` 同输入 → 结果一致
  - 测试文件独立（如 `src/index.test.ts`/`mcp-server.test.ts`），与 6.1/6.2 不共享文件
  - 验证：`bun test` 相关用例全部通过
  - _Requirements: 1.4, 8.1, 9.1, 9.2, 9.3_
  - _Boundary: WebServer, MCPServer_
  - _Depends: 4.1, 5.1_
