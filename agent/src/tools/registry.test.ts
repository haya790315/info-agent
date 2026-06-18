/**
 * ToolRegistry の単体テスト（KbClient をフェイク注入）
 */
import { describe, expect, test } from "bun:test";

import { KbApiError, type KbClient } from "./kbClient";
import { createToolRegistry, getTool } from "./registry";

/** 既定は空を返し、必要な部分だけ上書きする KbClient フェイク */
function fakeKb(overrides: Partial<KbClient> = {}): KbClient {
  return {
    search: async () => [],
    listDocuments: async () => [],
    getDocument: async () => null,
    ...overrides,
  };
}

describe("ToolRegistry", () => {
  test("search_knowledge_base 空結果は {ok:true,data:[]}", async () => {
    const reg = createToolRegistry(fakeKb({ search: async () => [] }));
    const tool = getTool(reg, "search_knowledge_base");
    expect(await tool.execute({ query: "x" })).toEqual({ ok: true, data: [] });
  });

  test("search_knowledge_base は引数不正で {ok:false}", async () => {
    const reg = createToolRegistry(fakeKb());
    const tool = getTool(reg, "search_knowledge_base");
    const result = await tool.execute({});
    expect(result.ok).toBe(false);
  });

  test("KbApiError は {ok:false} に変換される", async () => {
    const reg = createToolRegistry(
      fakeKb({
        search: async () => {
          throw new KbApiError("上流ダウン", 500);
        },
      }),
    );
    const tool = getTool(reg, "search_knowledge_base");
    const result = await tool.execute({ query: "x" });
    expect(result.ok).toBe(false);
  });

  test("get_document_detail は不存在で {ok:false,error:文档不存在}", async () => {
    const reg = createToolRegistry(fakeKb({ getDocument: async () => null }));
    const tool = getTool(reg, "get_document_detail");
    expect(await tool.execute({ document_id: 999 })).toEqual({
      ok: false,
      error: "文档不存在",
    });
  });

  test("3 つのツールが登録されている", () => {
    const reg = createToolRegistry(fakeKb());
    expect(reg.map((t) => t.name).sort()).toEqual([
      "get_document_detail",
      "list_documents",
      "search_knowledge_base",
    ]);
  });

  test("getTool は未知のツールで例外", () => {
    const reg = createToolRegistry(fakeKb());
    expect(() => getTool(reg, "nope")).toThrow();
  });
});
