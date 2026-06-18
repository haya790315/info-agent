/**
 * サービス全体で共有する型定義
 * Django REST API の契約に対応する DTO、会話メッセージ、ツール定義など。
 * any は使用せず、unknown または判別共用体で表現する。
 */
import type { ZodType } from "zod";

// ===== 会話メッセージ（OpenAI Chat Completions のロールに対応）=====

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

// ===== ナレッジベース DTO（Django 契約に対応、camelCase）=====

export interface SearchResultItem {
  content: string;
  filename: string;
  documentId: number;
  fileUrl: string | null;
  /** コサイン距離（小さいほど関連）。閾値フィルタに使う。未提供なら null */
  distance: number | null;
}

export interface DocumentSummary {
  id: number;
  filename: string;
  status: string;
  chunkCount: number;
  /** ISO 8601 */
  uploadedAt: string;
  errorMessage: string;
  fileUrl: string | null;
}

export type DocumentDetail = DocumentSummary;

// ===== ツール定義（Agent と MCP が共有する単一定義源）=====

/** ツール実行結果の判別共用体 */
export type ToolResult =
  | { ok: true; data: unknown }
  | { ok: false; error: string };

/** 1 つのツールの定義（name / description / zod パラメータ / 実行関数） */
export interface ToolDefinition<TArgs> {
  name: string;
  description: string;
  parameters: ZodType<TArgs>;
  execute(args: TArgs): Promise<ToolResult>;
}

/**
 * 型消去済みツール定義（レジストリ・アダプタが扱う統一形）。
 * execute は unknown を受け取り内部で zod 検証するため、異種ツールを 1 配列に格納できる。
 */
export interface ErasedToolDefinition {
  name: string;
  description: string;
  /** OpenAI Function Calling 用の JSON Schema */
  jsonSchema: Record<string, unknown>;
  /** ランタイム検証 / MCP inputSchema 用の zod スキーマ */
  parameters: ZodType<unknown>;
  /** 生の引数を受け取り、zod 検証後に実行する */
  execute(rawArgs: unknown): Promise<ToolResult>;
}
