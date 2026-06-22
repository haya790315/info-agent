/**
 * LLMClient: OpenAI Chat Completions の Function Calling 呼び出しを封装する。
 * 会話状態は持たない（履歴は呼び出し側が渡す）。失敗時は LLMError を投げる。
 */
import OpenAI from "openai";

import type { Config } from "./config";
import type { AssistantTurn, ChatMessage, LLMClient, LLMToolSpec } from "./types";

export class LLMError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LLMError";
  }
}

/** Chat Completions 呼び出しのポート（テストでモック注入できるよう抽象化） */
export interface ChatCompletionPort {
  create(params: {
    model: string;
    messages: ReadonlyArray<Record<string, unknown>>;
    tools?: ReadonlyArray<Record<string, unknown>>;
    tool_choice?: "auto" | "none";
  }): Promise<{
    choices: Array<{
      message: {
        content: string | null;
        tool_calls?: Array<{
          id: string;
          function: { name: string; arguments: string };
        }>;
      };
    }>;
  }>;
}

// OpenAI 応答の最小形（このファイル内でのみ使う）
interface OpenAIResponseMessage {
  content: string | null;
  tool_calls?: Array<{ id: string; function: { name: string; arguments: string } }>;
}
interface OpenAIChatResponse {
  choices: Array<{ message: OpenAIResponseMessage }>;
}

/** 本サービスの ChatMessage を OpenAI メッセージ形へ変換する */
function toOpenAIMessage(message: ChatMessage): Record<string, unknown> {
  switch (message.role) {
    case "system":
      return { role: "system", content: message.content };
    case "user":
      return { role: "user", content: message.content };
    case "assistant": {
      const base: Record<string, unknown> = {
        role: "assistant",
        content: message.content,
      };
      if (message.toolCalls && message.toolCalls.length > 0) {
        base.tool_calls = message.toolCalls.map((tc) => ({
          id: tc.id,
          type: "function",
          function: { name: tc.name, arguments: tc.argumentsJson },
        }));
      }
      return base;
    }
    case "tool":
      return {
        role: "tool",
        tool_call_id: message.toolCallId,
        content: message.content,
      };
  }
}

function toOpenAITool(tool: LLMToolSpec): Record<string, unknown> {
  return {
    type: "function",
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.jsonSchema,
    },
  };
}

/** OpenAI SDK を用いた実ポート */
function openAIPort(config: Config): ChatCompletionPort {
  const client = new OpenAI({
    apiKey: config.openaiApiKey,
    baseURL: config.openaiBaseUrl,
  });
  return {
    async create(params) {
      const res = await client.chat.completions.create(
        params as unknown as Parameters<typeof client.chat.completions.create>[0],
      );
      return res as unknown as OpenAIChatResponse;
    },
  };
}

/**
 * LLMClient を生成する。
 * @param config OpenAI 設定（apiKey/model/baseUrl）
 * @param port Chat Completions ポート（テスト用に注入可能、既定は OpenAI SDK 実装）
 */
export function createLLMClient(
  config: Config,
  port: ChatCompletionPort = openAIPort(config),
): LLMClient {
  return {
    async chat(messages: ChatMessage[], tools: LLMToolSpec[]): Promise<AssistantTurn> {
      const oaMessages = messages.map(toOpenAIMessage);
      const oaTools = tools.length > 0 ? tools.map(toOpenAITool) : undefined;

      let res: OpenAIChatResponse;
      try {
        res = await port.create({
          model: config.openaiModel,
          messages: oaMessages,
          tools: oaTools,
          tool_choice: oaTools ? "auto" : undefined,
        });
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        throw new LLMError(`LLM 呼び出しに失敗しました: ${detail}`);
      }

      const message = res.choices[0]?.message;
      if (!message) {
        throw new LLMError("LLM 応答に choices が含まれていません");
      }

      return {
        content: message.content,
        toolCalls: (message.tool_calls ?? []).map((tc) => ({
          id: tc.id,
          name: tc.function.name,
          argumentsJson: tc.function.arguments,
        })),
      };
    },
  };
}
