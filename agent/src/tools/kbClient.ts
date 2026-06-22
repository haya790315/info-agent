/**
 * KbClient: ナレッジベース Django REST API のクライアント実装。
 * Django の snake_case JSON を camelCase DTO に変換する（マッピングはこの境界で完結）。
 */
import type { DocumentDetail, DocumentSummary, KbClient, SearchResultItem } from "../types";

export type { KbClient };

/** 上流 API のエラー（到達不能 / 404 以外の非 2xx） */
export class KbApiError extends Error {
  readonly status: number | undefined;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "KbApiError";
    this.status = status;
  }
}

/** fetch の型（テストでモック注入できるようにする） */
type FetchFn = typeof fetch;

// Django から返る生の形（snake_case、このファイル内のみ）
interface RawSearchItem {
  content: string;
  filename: string;
  category: string;
  document_id: number;
  file_url: string | null;
  distance?: number | null;
}
interface RawDocument {
  id: number;
  filename: string;
  status: string;
  chunk_count: number;
  uploaded_at: string;
  error_message: string;
  file_url: string | null;
}

function mapSearchItem(raw: RawSearchItem): SearchResultItem {
  return {
    content: raw.content,
    filename: raw.filename,
    category: raw.category ?? "",
    documentId: raw.document_id,
    fileUrl: raw.file_url,
    distance: raw.distance ?? null,
  };
}

function mapDocument(raw: RawDocument): DocumentSummary {
  return {
    id: raw.id,
    filename: raw.filename,
    status: raw.status,
    chunkCount: raw.chunk_count,
    uploadedAt: raw.uploaded_at,
    errorMessage: raw.error_message,
    fileUrl: raw.file_url,
  };
}

/**
 * KbClient を生成する。
 * @param baseUrl Django サービスの base URL（末尾スラッシュは除去）
 * @param fetchFn fetch 実装（テスト用に注入可能、既定はグローバル fetch）
 */
export function createKbClient(baseUrl: string, fetchFn: FetchFn = fetch): KbClient {
  const base = baseUrl.replace(/\/+$/, "");

  return {
    async search(query: string, category?: string): Promise<SearchResultItem[]> {
      const body: Record<string, string> = { query };
      if (category) body.category = category;
      const res = await fetchFn(`${base}/api/search/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new KbApiError(`検索 API が失敗しました: ${res.status}`, res.status);
      }
      const data = (await res.json()) as { results?: RawSearchItem[] };
      return (data.results ?? []).map(mapSearchItem);
    },

    async listDocuments(): Promise<DocumentSummary[]> {
      const res = await fetchFn(`${base}/api/documents/`);
      if (!res.ok) {
        throw new KbApiError(`一覧 API が失敗しました: ${res.status}`, res.status);
      }
      const data = (await res.json()) as { documents?: RawDocument[] };
      return (data.documents ?? []).map(mapDocument);
    },

    async getDocument(documentId: number): Promise<DocumentDetail | null> {
      const res = await fetchFn(`${base}/api/documents/${documentId}/`);
      if (res.status === 404) {
        return null;
      }
      if (!res.ok) {
        throw new KbApiError(`詳細 API が失敗しました: ${res.status}`, res.status);
      }
      const data = (await res.json()) as RawDocument;
      return mapDocument(data);
    },
  };
}
