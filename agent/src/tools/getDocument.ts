/**
 * get_document_detail ツール定義
 * ドキュメントのメタ情報（状態・チャンク数など）のみを返す。
 * 文書の本文は含まれないため、内容の問い合わせには search_knowledge_base を使うこと。
 */
import { z } from "zod";

import type { KbClient } from "../types";
import { defineTool, guarded } from "./helpers";

export function createGetDocumentTool(kb: KbClient) {
  return defineTool({
    name: "get_document_detail",
    description:
      "指定したドキュメントの【メタ情報のみ】（ファイル名・処理状態・チャンク数・アップロード日時）を返す。本文・内容は含まれない。文書の中身に関する質問には使わず、search_knowledge_base を使うこと。",
    jsonSchema: {
      type: "object",
      properties: {
        document_id: { type: "number", description: "ドキュメントID" },
      },
      required: ["document_id"],
    },
    parameters: z.object({ document_id: z.number().int() }),
    run: ({ document_id }) =>
      guarded(async () => {
        const doc = await kb.getDocument(document_id);
        if (doc === null) {
          return { ok: false, error: "文書が見つかりません" };
        }
        return { ok: true, data: doc };
      }),
  });
}
