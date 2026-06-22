/**
 * ツール定義のユーティリティ
 * defineTool: 型付き run を型消去済み ErasedToolDefinition に包む。
 * guarded: KbApiError を {ok:false} に変換し、想定外エラーは再送出する。
 */
import type { ZodType } from "zod";

import type { ErasedToolDefinition, ToolResult } from "../types";
import { KbApiError } from "./kbClient";

/** 型付きの run を型消去済みツールに包む */
export function defineTool<T>(opts: {
  name: string;
  description: string;
  jsonSchema: Record<string, unknown>;
  parameters: ZodType<T>;
  run: (args: T) => Promise<ToolResult>;
}): ErasedToolDefinition {
  return {
    name: opts.name,
    description: opts.description,
    jsonSchema: opts.jsonSchema,
    parameters: opts.parameters as ZodType<unknown>,
    async execute(rawArgs: unknown): Promise<ToolResult> {
      const parsed = opts.parameters.safeParse(rawArgs);
      if (!parsed.success) {
        return { ok: false, error: `引数が不正です: ${parsed.error.message}` };
      }
      return opts.run(parsed.data);
    },
  };
}

/** KbApiError を {ok:false} に変換し、想定外エラーは再送出する */
export async function guarded(fn: () => Promise<ToolResult>): Promise<ToolResult> {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof KbApiError) {
      return { ok: false, error: err.message };
    }
    throw err;
  }
}
