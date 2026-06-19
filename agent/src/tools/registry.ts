/**
 * ToolRegistry: 3 つのツールの単一定義源。
 * 各 execute がツールの業務ロジックの唯一の所在で、Agent と MCP が共通で消費する。
 * KbClient 経由でナレッジベース REST API を呼ぶ。
 */
import { z, type ZodType } from "zod";

import type { ErasedToolDefinition, ToolResult } from "../types";
import { KbApiError, type KbClient } from "./kbClient";

/** 型付きの run を型消去済みツールに包む */
function defineTool<T>(opts: {
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

/** KbApiError を {ok:false} に変換し、それ以外の想定外エラーは再送出する */
async function guarded(fn: () => Promise<ToolResult>): Promise<ToolResult> {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof KbApiError) {
      return { ok: false, error: err.message };
    }
    throw err;
  }
}

/**
 * 3 つのツールを定義したレジストリを生成する。
 * @param kb ナレッジベースクライアント
 * @param maxDistance 採用するコサイン距離の上限（これより大きい結果は破棄）。既定は Infinity（フィルタ無効）
 */
export function createToolRegistry(
  kb: KbClient,
  maxDistance: number = Infinity,
): ErasedToolDefinition[] {
  return [
    defineTool({
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
          const all = await kb.search(query, category);
          // 関連度の薄い（距離が閾値を超える）結果を破棄してノイズを抑える。
          // distance が null（未提供）の結果は安全側で残す。
          const relevant = all.filter(
            (r) => r.distance === null || r.distance <= maxDistance,
          );
          return { ok: true, data: relevant };
        }),
    }),

    defineTool({
      name: "list_documents",
      description:
        "ナレッジベース内の全ドキュメント一覧を返す。「どんな資料がある」などの質問に使う。",
      jsonSchema: { type: "object", properties: {} },
      parameters: z.object({}),
      run: () =>
        guarded(async () => ({ ok: true, data: await kb.listDocuments() })),
    }),

    defineTool({
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
            return { ok: false, error: "文档不存在" };
          }
          return { ok: true, data: doc };
        }),
    }),
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
