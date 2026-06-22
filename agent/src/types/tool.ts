/** ツール定義層の型定義。Agent と MCP が共有する単一定義源。 */
import type { ZodType } from "zod";

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
