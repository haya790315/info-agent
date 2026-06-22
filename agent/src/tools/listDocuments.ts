/**
 * list_documents ツール定義
 * 全ドキュメントのファイル名・種別・状態一覧を返す。
 * 固有名詞検索（人名・会社名）はファイル名でしか照合できないため、このツールが起点になる。
 */
import { z } from "zod";

import type { KbClient } from "../types";
import { defineTool, guarded } from "./helpers";

export function createListDocumentsTool(kb: KbClient) {
  return defineTool({
    name: "list_documents",
    description:
      "ナレッジベース内の全ドキュメント一覧（ファイル名・種別・状態）を返す。「どんな資料がある」などの質問に使う。" +
      "また、人名・会社名・製品名などの固有名詞は本文ではなくファイル名にしか含まれないことが多いため、" +
      "『〇〇について知っているか』『〇〇の職歴書はあるか』のような固有名詞の問い合わせでは、まずこのツールでファイル名一覧を確認すること。",
    jsonSchema: { type: "object", properties: {} },
    parameters: z.object({}),
    run: () => guarded(async () => ({ ok: true, data: await kb.listDocuments() })),
  });
}
