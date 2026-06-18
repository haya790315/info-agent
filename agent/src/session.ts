/**
 * SessionStore: セッション単位の会話履歴（インメモリ）
 * 永続化なし（プロセス再起動で消失）。sessionId ごとに履歴を隔離する。
 */
import type { ChatMessage } from "./types";

export interface SessionStore {
  /** 履歴を取得する（未知の sessionId は [] を返す） */
  getHistory(sessionId: string): ChatMessage[];
  /** 1 件以上のメッセージを末尾に追加する */
  append(sessionId: string, ...messages: ChatMessage[]): void;
}

/**
 * インメモリ SessionStore を生成する。
 * 内部は Map<sessionId, ChatMessage[]> で、セッション間は完全に隔離される。
 */
export function createSessionStore(): SessionStore {
  const sessions = new Map<string, ChatMessage[]>();

  return {
    getHistory(sessionId: string): ChatMessage[] {
      return sessions.get(sessionId) ?? [];
    },

    append(sessionId: string, ...messages: ChatMessage[]): void {
      const existing = sessions.get(sessionId);
      if (existing) {
        existing.push(...messages);
      } else {
        sessions.set(sessionId, [...messages]);
      }
    },
  };
}
