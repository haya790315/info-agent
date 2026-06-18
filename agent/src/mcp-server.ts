/**
 * MCPServer: stdio で MCP プロトコル経由に同一のツール群を公開する。
 * Agent と同じ ToolRegistry.execute を呼ぶため、同入力なら結果は一致する（要件 9.3）。
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import type { ZodRawShape } from "zod";

import { loadConfig } from "./config";
import { createKbClient } from "./tools/kbClient";
import { createToolRegistry } from "./tools/registry";
import type { ErasedToolDefinition } from "./types";

/** MCP のツール結果（text content） */
interface McpToolResult {
  content: Array<{ type: "text"; text: string }>;
  isError?: boolean;
}

/** zod スキーマから ZodRawShape（フィールド定義）を取り出す */
function shapeOf(tool: ErasedToolDefinition): ZodRawShape {
  const maybe = tool.parameters as unknown as { shape?: ZodRawShape };
  return maybe.shape ?? {};
}

/**
 * ツールの execute を MCP ハンドラに包む。
 * Agent 内部と同一の execute を呼ぶため、結果は一貫する。
 */
export function makeHandler(
  tool: ErasedToolDefinition,
): (args: unknown) => Promise<McpToolResult> {
  return async (args: unknown): Promise<McpToolResult> => {
    const result = await tool.execute(args);
    const payload = result.ok ? result.data : { error: result.error };
    return {
      content: [{ type: "text", text: JSON.stringify(payload) }],
      isError: !result.ok,
    };
  };
}

/** レジストリから MCP サーバを構築する */
export function buildMcpServer(registry: ErasedToolDefinition[]): McpServer {
  const server = new McpServer({ name: "kb-agent", version: "0.1.0" });
  for (const tool of registry) {
    server.registerTool(
      tool.name,
      { description: tool.description, inputSchema: shapeOf(tool) },
      makeHandler(tool) as never,
    );
  }
  return server;
}

// 直接実行時のみ stdio で起動する
if (import.meta.main) {
  const config = loadConfig();
  const kb = createKbClient(config.kbApiBaseUrl);
  const registry = createToolRegistry(kb);
  const server = buildMcpServer(registry);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}
