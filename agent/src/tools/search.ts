/**
 * search_knowledge_base ツール定義
 * 意味検索でナレッジベースの関連チャンクを取得する。
 */
import { z } from "zod";

import type { KbClient } from "../types";
import { defineTool, guarded } from "./helpers";

export function createSearchTool(kb: KbClient) {
  return defineTool({
    name: "search_knowledge_base",
    description:
      "ナレッジベースを意味検索し、関連する文書チャンクの【本文】を返す。文書の内容に関する質問（「XXXとは」「XXXの方法」「XXXについて教えて」など）には必ずこれを使う。" +
      "特定の種別（職歴書・マニュアルなど）に絞りたいときは category を指定する。" +
      "指定できる category 値: resume（職歴書・履歴書）, manual（マニュアル・操作手順）, policy（規程・ポリシー）, technical（技術資料）, report（レポート・報告書）, other（その他）。省略時は全種別を横断検索する。",
    jsonSchema: {
      type: "object",
      properties: {
        query:    { type: "string", description: "検索クエリ" },
        category: {
          type: "string",
          description: "ドキュメント種別フィルタ（省略可）: resume / manual / policy / technical / report / other",
        },
      },
      required: ["query"],
    },
    parameters: z.object({
      query:    z.string().min(1),
      category: z.string().optional(),
    }),
    run: ({ query, category }) =>
      guarded(async () => {
        // サーバ側で関連性フィルタ済みのため、結果はそのまま返す
        const results = await kb.search(query, category);
        return { ok: true, data: results };
      }),
  });
}
