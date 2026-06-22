/**
 * 会話・LLM 層の型定義
 * OpenAI Chat Completions のロールに対応するメッセージ型と、
 * LLM クライアントのインターフェース。
 */

export type ChatMessage =
  | { role: "system"; content: string }
  | { role: "user"; content: string }
  | { role: "assistant"; content: string | null; toolCalls?: ToolCall[] }
  | { role: "tool"; toolCallId: string; content: string };

/** LLM が要求したツール呼び出し */
export interface ToolCall {
  id: string;
  name: string;
  /** 引数の JSON 文字列（実行前に zod でパースする） */
  argumentsJson: string;
}

/** LLM の 1 ターン分の応答 */
export interface AssistantTurn {
  content: string | null;
  toolCalls: ToolCall[];
}

/** LLM に渡すツール仕様（JSON Schema 化したもの） */
export interface LLMToolSpec {
  name: string;
  description: string;
  jsonSchema: Record<string, unknown>;
}

/** LLM クライアント（Agent が依存する抽象、テストでモック注入可能） */
export interface LLMClient {
  chat(messages: ChatMessage[], tools: LLMToolSpec[]): Promise<AssistantTurn>;
}
