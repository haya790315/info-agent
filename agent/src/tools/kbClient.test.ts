/**
 * KbClient の単体テスト（fetch をモック注入）
 */
import { describe, expect, test } from "bun:test";

import { createKbClient, KbApiError } from "./kbClient";

/** 指定の body/status を返す fetch モック */
function fetchReturning(body: unknown, status = 200): typeof fetch {
  return (async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as unknown as typeof fetch;
}

describe("KbClient", () => {
  test("search は snake_case を camelCase に変換する", async () => {
    const kb = createKbClient(
      "http://x",
      fetchReturning({
        results: [
          {
            content: "年休は10日",
            filename: "手册.pdf",
            category: "policy",
            document_id: 3,
            file_url: "http://x/media/pdfs/手册.pdf",
            distance: 0.42,
          },
        ],
      }),
    );
    const results = await kb.search("年休");
    expect(results).toEqual([
      {
        content: "年休は10日",
        filename: "手册.pdf",
        category: "policy",
        documentId: 3,
        fileUrl: "http://x/media/pdfs/手册.pdf",
        distance: 0.42,
      },
    ]);
  });

  test("search 空結果は [] を返す", async () => {
    const kb = createKbClient("http://x", fetchReturning({ results: [] }));
    expect(await kb.search("q")).toEqual([]);
  });

  test("getDocument は 404 で null を返す", async () => {
    const kb = createKbClient("http://x", fetchReturning({ error: "nf" }, 404));
    expect(await kb.getDocument(999)).toBeNull();
  });

  test("getDocument は 404 以外の非 2xx で KbApiError を投げる", async () => {
    const kb = createKbClient("http://x", fetchReturning({}, 500));
    await expect(kb.getDocument(1)).rejects.toBeInstanceOf(KbApiError);
  });

  test("listDocuments は変換し、空配列も扱える", async () => {
    const kb = createKbClient(
      "http://x",
      fetchReturning({
        documents: [
          {
            id: 1,
            filename: "a.pdf",
            status: "complete",
            chunk_count: 2,
            uploaded_at: "2026-06-18T00:00:00Z",
            error_message: "",
            file_url: null,
          },
        ],
      }),
    );
    const docs = await kb.listDocuments();
    expect(docs[0]).toEqual({
      id: 1,
      filename: "a.pdf",
      status: "complete",
      chunkCount: 2,
      uploadedAt: "2026-06-18T00:00:00Z",
      errorMessage: "",
      fileUrl: null,
    });
  });
});
