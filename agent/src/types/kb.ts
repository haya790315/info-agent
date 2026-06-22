/**
 * ナレッジベース層の型定義
 * Django REST API との契約（DTO）と KbClient インターフェース。
 * フィールド名は Django の snake_case を camelCase に変換した形。
 */

export interface SearchResultItem {
  content: string;
  filename: string;
  /** ドキュメント種別（未設定は空文字）*/
  category: string;
  documentId: number;
  fileUrl: string | null;
  /** コサイン距離（小さいほど関連）。閾値フィルタに使う。未提供なら null */
  distance: number | null;
}

export interface DocumentSummary {
  id: number;
  filename: string;
  status: string;
  chunkCount: number;
  /** ISO 8601 */
  uploadedAt: string;
  errorMessage: string;
  fileUrl: string | null;
}

export type DocumentDetail = DocumentSummary;

/** ナレッジベース Django REST API のクライアントインターフェース */
export interface KbClient {
  /** POST /api/search/ {query, category?} → 関連チャンク（空なら []） */
  search(query: string, category?: string): Promise<SearchResultItem[]>;
  /** GET /api/documents/ → 全ドキュメント（空なら []） */
  listDocuments(): Promise<DocumentSummary[]>;
  /** GET /api/documents/<id>/ → ドキュメント詳細（存在しなければ null） */
  getDocument(documentId: number): Promise<DocumentDetail | null>;
}
