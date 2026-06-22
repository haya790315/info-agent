/**
 * SessionStore の単体テスト
 */
import { describe, expect, test } from "bun:test";

import { createSessionStore } from "../session";
import type { ChatMessage } from "../types";

const userMsg = (text: string): ChatMessage => ({ role: "user", content: text });

describe("SessionStore", () => {
  test("未知の sessionId は [] を返す", () => {
    const store = createSessionStore();
    expect(store.getHistory("unknown")).toEqual([]);
  });

  test("append 後に順序通り取得できる", () => {
    const store = createSessionStore();
    store.append("s1", userMsg("a"));
    store.append("s1", userMsg("b"), userMsg("c"));
    const history = store.getHistory("s1");
    expect(history.map((m) => (m.role === "user" ? m.content : ""))).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  test("異なる sessionId の履歴は隔離される", () => {
    const store = createSessionStore();
    store.append("s1", userMsg("s1-only"));
    store.append("s2", userMsg("s2-only"));
    expect(store.getHistory("s1")).toHaveLength(1);
    expect(store.getHistory("s2")).toHaveLength(1);
    const s1First = store.getHistory("s1")[0];
    expect(s1First && s1First.role === "user" ? s1First.content : "").toBe(
      "s1-only",
    );
  });
});
