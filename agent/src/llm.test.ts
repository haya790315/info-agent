/**
 * LLMClient の単体テスト（ChatCompletionPort をモック注入）
 */
import { describe, expect, test } from "bun:test";

import type { Config } from "./config";
import { type ChatCompletionPort, createLLMClient, LLMError } from "./llm";

const config: Config = {
  openaiApiKey: "key",
  openaiModel: "test-model",
  openaiBaseUrl: undefined,
  kbApiBaseUrl: "http://localhost:8000",
};

type CreateParams = Parameters<ChatCompletionPort["create"]>[0];

describe("LLMClient", () => {
  test("content と tool_calls を解析する", async () => {
    const port: ChatCompletionPort = {
      create: async () => ({
        choices: [
          {
            message: {
              content: null,
              tool_calls: [
                {
                  id: "t1",
                  function: {
                    name: "search_knowledge_base",
                    arguments: '{"query":"x"}',
                  },
                },
              ],
            },
          },
        ],
      }),
    };
    const llm = createLLMClient(config, port);
    const turn = await llm.chat(
      [{ role: "user", content: "hi" }],
      [{ name: "search_knowledge_base", description: "d", jsonSchema: { type: "object" } }],
    );
    expect(turn.content).toBeNull();
    expect(turn.toolCalls).toEqual([
      { id: "t1", name: "search_knowledge_base", argumentsJson: '{"query":"x"}' },
    ]);
  });

  test("messages と tools をポートへ渡す", async () => {
    let captured: CreateParams | undefined;
    const port: ChatCompletionPort = {
      create: async (params) => {
        captured = params;
        return { choices: [{ message: { content: "ok" } }] };
      },
    };
    const llm = createLLMClient(config, port);
    await llm.chat(
      [{ role: "user", content: "hi" }],
      [{ name: "list_documents", description: "d", jsonSchema: { type: "object" } }],
    );
    expect(captured?.model).toBe("test-model");
    expect(captured?.messages).toHaveLength(1);
    expect(captured?.tools).toHaveLength(1);
    expect(captured?.tool_choice).toBe("auto");
  });

  test("tools が空なら tool_choice を送らない", async () => {
    let captured: CreateParams | undefined;
    const port: ChatCompletionPort = {
      create: async (params) => {
        captured = params;
        return { choices: [{ message: { content: "final" } }] };
      },
    };
    const llm = createLLMClient(config, port);
    const turn = await llm.chat([{ role: "user", content: "hi" }], []);
    expect(captured?.tools).toBeUndefined();
    expect(turn.content).toBe("final");
    expect(turn.toolCalls).toEqual([]);
  });

  test("ポート失敗時は LLMError を投げる", async () => {
    const port: ChatCompletionPort = {
      create: async () => {
        throw new Error("boom");
      },
    };
    const llm = createLLMClient(config, port);
    await expect(
      llm.chat([{ role: "user", content: "hi" }], []),
    ).rejects.toBeInstanceOf(LLMError);
  });
});
