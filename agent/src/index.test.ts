/**
 * WebServer /api/chat の結合テスト（AgentService をモック注入）
 */
import { describe, expect, test } from "bun:test";

import { createApp } from "./index";
import type { AgentService } from "./agent";

function mockAgent(): { agent: AgentService; calls: string[] } {
  const calls: string[] = [];
  const agent: AgentService = {
    run: async (_sessionId, message) => {
      calls.push(message);
      return { answer: `回答: ${message}` };
    },
  };
  return { agent, calls };
}

describe("POST /api/chat", () => {
  test("空 message は 400 を返し、agent を呼ばない", async () => {
    const { agent, calls } = mockAgent();
    const app = createApp(agent, () => "fixed");
    const res = await app.request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "   " }),
    });
    expect(res.status).toBe(400);
    const json = (await res.json()) as { error?: string };
    expect(json.error).toBeTruthy();
    expect(calls).toHaveLength(0);
  });

  test("正常な message は 200 で answer と sessionId を返す", async () => {
    const { agent } = mockAgent();
    const app = createApp(agent, () => "fixed-id");
    const res = await app.request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "年休は？" }),
    });
    expect(res.status).toBe(200);
    const json = (await res.json()) as { answer: string; sessionId: string };
    expect(json.answer).toContain("年休は？");
    expect(json.sessionId).toBe("fixed-id");
  });

  test("sessionId 指定時はそれを引き継ぐ", async () => {
    const { agent } = mockAgent();
    const app = createApp(agent, () => "generated");
    const res = await app.request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "次", sessionId: "s-123" }),
    });
    const json = (await res.json()) as { sessionId: string };
    expect(json.sessionId).toBe("s-123");
  });
});
