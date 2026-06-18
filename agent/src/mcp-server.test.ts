/**
 * MCP ハンドラの一貫性テスト（要件 9.3）
 * MCP アダプタ経由の結果が、同一入力での registry.execute と一致することを検証する。
 */
import { describe, expect, test } from "bun:test";

import { makeHandler } from "./mcp-server";
import { createToolRegistry, getTool } from "./tools/registry";
import type { KbClient } from "./tools/kbClient";

function fakeKb(overrides: Partial<KbClient> = {}): KbClient {
  return {
    search: async () => [],
    listDocuments: async () => [],
    getDocument: async () => null,
    ...overrides,
  };
}

describe("MCP ハンドラ一貫性", () => {
  test("MCP の text は同一入力の registry.execute の data と一致する", async () => {
    const registry = createToolRegistry(
      fakeKb({
        search: async () => [
          { content: "c", filename: "f.pdf", documentId: 1, fileUrl: "http://x/f.pdf" },
        ],
      }),
    );
    const tool = getTool(registry, "search_knowledge_base");
    const args = { query: "q" };

    const direct = await tool.execute(args);
    const viaMcp = await makeHandler(tool)(args);

    const directText = JSON.stringify(direct.ok ? direct.data : { error: direct.error });
    const firstContent = viaMcp.content[0];
    expect(firstContent?.text).toBe(directText);
    expect(viaMcp.isError).toBe(false);
  });

  test("失敗時は isError=true でエラーを返す", async () => {
    const registry = createToolRegistry(fakeKb({ getDocument: async () => null }));
    const tool = getTool(registry, "get_document_detail");
    const viaMcp = await makeHandler(tool)({ document_id: 999 });
    expect(viaMcp.isError).toBe(true);
    expect(viaMcp.content[0]?.text).toContain("文档不存在");
  });
});
