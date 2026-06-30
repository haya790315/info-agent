/**
 * ToolRegistry: 3 つのツールを組み合わせて単一のレジストリを生成する。
 * Agent と MCP が共通でこのレジストリを消費する。
 */
import type { ErasedToolDefinition, KbClient } from "../types";
import { createGetDocumentTool } from "./getDocument";
import { createListDocumentsTool } from "./listDocuments";
import { createSearchTool } from "./search";

/**
 * 3 つのツールを定義したレジストリを生成する。
 * @param kb ナレッジベースクライアント
 */
export function createToolRegistry(
  kb: KbClient,
): ErasedToolDefinition[] {
  return [
    createSearchTool(kb),
    createListDocumentsTool(kb),
    createGetDocumentTool(kb),
  ];
}

/** レジストリから名前でツールを取得する（存在しなければ例外） */
export function getTool(
  registry: ErasedToolDefinition[],
  name: string,
): ErasedToolDefinition {
  const tool = registry.find((t) => t.name === name);
  if (!tool) {
    throw new Error(`未知のツール: ${name}`);
  }
  return tool;
}
