/**
 * AgentLoop の結合テスト（LLMClient をモック、ToolRegistry はフェイク KbClient で構築）
 */
import { describe, expect, test } from "bun:test";

import { createAgentLoop } from "./agent";
import { LLMError, type LLMClient } from "./llm";
import { createSessionStore } from "./session";
import { createToolRegistry } from "./tools/registry";
import type { KbClient } from "./tools/kbClient";
import type { AssistantTurn, ChatMessage, LLMToolSpec } from "./types";

function fakeKb(overrides: Partial<KbClient> = {}): KbClient {
  return {
    search: async () => [],
    listDocuments: async () => [],
    getDocument: async () => null,
    ...overrides,
  };
}

/** スクリプト化した turn を順に返す LLM モック。各呼び出しの (messages, tools) を記録する */
function scriptedLLM(turns: AssistantTurn[]): {
  llm: LLMClient;
  calls: Array<{ messages: ChatMessage[]; tools: LLMToolSpec[] }>;
} {
  const calls: Array<{ messages: ChatMessage[]; tools: LLMToolSpec[] }> = [];
  const llm: LLMClient = {
    chat: async (messages, tools) => {
      calls.push({ messages: [...messages], tools: [...tools] });
      return turns[calls.length - 1] ?? { content: "(no more)", toolCalls: [] };
    },
  };
  return { llm, calls };
}

const toolCallTurn: AssistantTurn = {
  content: null,
  toolCalls: [
    { id: "t1", name: "search_knowledge_base", argumentsJson: '{"query":"年休"}' },
  ],
};

describe("AgentLoop", () => {
  test("工具往復後、回答末尾に確定的な出典ブロックが付く", async () => {
    const registry = createToolRegistry(
      fakeKb({
        search: async () => [
          {
            content: "年休は10日",
            filename: "手册.pdf",
            category: "policy",
            documentId: 1,
            fileUrl: "http://x/media/pdfs/手册.pdf",
            distance: 0.3,
          },
        ],
      }),
    );
    const { llm } = scriptedLLM([
      toolCallTurn,
      { content: "年休は10日です。", toolCalls: [] },
    ]);
    const agent = createAgentLoop({
      llm,
      registry,
      session: createSessionStore(),
      logger: { log: () => {} },
    });
    const reply = await agent.run("s1", "年休は？");
    expect(reply.answer).toContain("年休は10日です。");
    expect(reply.answer).toContain("手册.pdf");
    expect(reply.answer).toContain("http://x/media/pdfs/手册.pdf");
  });

  test("ツール不要の質問はツールを呼ばず直接回答", async () => {
    let searchCalled = false;
    const registry = createToolRegistry(
      fakeKb({
        search: async () => {
          searchCalled = true;
          return [];
        },
      }),
    );
    const { llm } = scriptedLLM([{ content: "こんにちは。", toolCalls: [] }]);
    const agent = createAgentLoop({
      llm,
      registry,
      session: createSessionStore(),
      logger: { log: () => {} },
    });
    const reply = await agent.run("s1", "やあ");
    expect(reply.answer).toContain("こんにちは。");
    expect(reply.answer).not.toContain("出典:");
    expect(searchCalled).toBe(false);
  });

  test("轮次上限到達でツール無効の収尾呼び出しが非空回答を返す", async () => {
    const registry = createToolRegistry(fakeKb());
    // 常に tool_calls を返し続け、最後にツール無効呼び出しで文字答案
    const { llm, calls } = scriptedLLM([
      toolCallTurn,
      toolCallTurn,
      { content: "現時点の情報でのまとめです。", toolCalls: [] },
    ]);
    const agent = createAgentLoop({
      llm,
      registry,
      session: createSessionStore(),
      maxToolRounds: 2,
      logger: { log: () => {} },
    });
    const reply = await agent.run("s1", "質問");
    expect(reply.answer).toContain("現時点の情報でのまとめです。");
    // 最後の呼び出しはツール無効（tools 空配列）であること
    const lastCall = calls[calls.length - 1];
    expect(lastCall?.tools).toEqual([]);
  });

  test("多輪：2 回目の呼び出しに 1 回目の履歴が含まれる", async () => {
    const registry = createToolRegistry(fakeKb());
    const session = createSessionStore();
    const { llm, calls } = scriptedLLM([
      { content: "回答1", toolCalls: [] },
      { content: "回答2", toolCalls: [] },
    ]);
    const agent = createAgentLoop({ llm, registry, session, logger: { log: () => {} } });
    await agent.run("s1", "質問1");
    await agent.run("s1", "質問2");
    const secondCallMessages = calls[1]?.messages ?? [];
    const hasFirstUser = secondCallMessages.some(
      (m) => m.role === "user" && m.content === "質問1",
    );
    const hasFirstAnswer = secondCallMessages.some(
      (m) => m.role === "assistant" && m.content !== null && m.content.includes("回答1"),
    );
    expect(hasFirstUser).toBe(true);
    expect(hasFirstAnswer).toBe(true);
  });

  test("LLM 失敗時は友好的なエラーを返し、クラッシュしない", async () => {
    const registry = createToolRegistry(fakeKb());
    const llm: LLMClient = {
      chat: async () => {
        throw new LLMError("boom");
      },
    };
    const agent = createAgentLoop({
      llm,
      registry,
      session: createSessionStore(),
      logger: { log: () => {} },
    });
    const reply = await agent.run("s1", "質問");
    expect(reply.answer.length).toBeGreaterThan(0);
    expect(reply.answer).toContain("回答を生成できません");
  });
});
