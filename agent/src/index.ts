/**
 * WebServer: Hono サーバ。
 * - GET /        → 静的な聊天ページ（public/index.html）
 * - GET /*       → 静的アセット（public 配下）
 * - POST /api/chat → {sessionId?, message} を受け、AgentLoop を実行して {answer, sessionId} を返す
 * createApp はテストで mock agent を注入できるよう分離。実起動は import.meta.main 内のみ。
 */
import { Hono } from "hono";
import { serveStatic } from "hono/bun";

import { createAgentLoop, type AgentService } from "./agent";
import { loadConfig } from "./config";
import { createLLMClient } from "./llm";
import { createSessionStore } from "./session";
import { createKbClient } from "./tools/kbClient";
import { createToolRegistry } from "./tools/registry";

interface ChatRequestBody {
  sessionId?: string;
  message?: string;
}

/**
 * Hono アプリを生成する（agent と id 生成器を注入可能）。
 */
export function createApp(
  agent: AgentService,
  generateId: () => string = () => crypto.randomUUID(),
): Hono {
  const app = new Hono();

  app.post("/api/chat", async (c) => {
    let body: ChatRequestBody;
    try {
      body = (await c.req.json()) as ChatRequestBody;
    } catch {
      body = {};
    }

    const message = typeof body.message === "string" ? body.message : "";
    if (message.trim().length === 0) {
      return c.json({ error: "質問を入力してください。" }, 400);
    }

    const sessionId =
      typeof body.sessionId === "string" && body.sessionId.length > 0
        ? body.sessionId
        : generateId();

    const reply = await agent.run(sessionId, message);
    return c.json({ answer: reply.answer, sessionId });
  });

  // 静的配信（チャット UI）
  app.get("/", serveStatic({ path: "./public/index.html" }));
  app.use("/*", serveStatic({ root: "./public" }));

  return app;
}

/** 実依存を組み立てて AgentService を構築する */
function buildAgent(): AgentService {
  const config = loadConfig();
  const kb = createKbClient(config.kbApiBaseUrl);
  const registry = createToolRegistry(kb, config.searchMaxDistance);
  const llm = createLLMClient(config);
  const session = createSessionStore();
  return createAgentLoop({ llm, registry, session });
}

// 直接実行時のみサーバを起動する（import 時は起動しない＝テストで env 不要）
if (import.meta.main) {
  const app = createApp(buildAgent());
  const port = Number(process.env.PORT ?? "3000");
  // eslint-disable-next-line no-console
  console.log(`agent server listening on http://localhost:${port}`);
  Bun.serve({ port, fetch: app.fetch });
}
