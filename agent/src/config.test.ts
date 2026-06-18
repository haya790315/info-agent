/**
 * config.ts の単体テスト
 */
import { describe, expect, test } from "bun:test";

import { loadConfig } from "./config";

describe("loadConfig", () => {
  test("必須の環境変数が欠落していればエラーを投げる", () => {
    expect(() => loadConfig({})).toThrow(/OPENAI_API_KEY/);
    // OPENAI_API_KEY のみ → KB_API_BASE_URL 欠落でエラー
    expect(() => loadConfig({ OPENAI_API_KEY: "key" })).toThrow(
      /KB_API_BASE_URL/,
    );
  });

  test("任意変数が無い場合は既定値を返す", () => {
    const config = loadConfig({
      OPENAI_API_KEY: "key",
      KB_API_BASE_URL: "http://localhost:8000",
    });
    expect(config.openaiModel).toBe("gpt-4o-mini");
    expect(config.openaiBaseUrl).toBeUndefined();
    expect(config.openaiApiKey).toBe("key");
    expect(config.kbApiBaseUrl).toBe("http://localhost:8000");
  });

  test("明示された任意変数を尊重する", () => {
    const config = loadConfig({
      OPENAI_API_KEY: "key",
      KB_API_BASE_URL: "http://localhost:8000",
      OPENAI_MODEL: "gpt-4o",
      OPENAI_BASE_URL: "https://example.com/v1",
    });
    expect(config.openaiModel).toBe("gpt-4o");
    expect(config.openaiBaseUrl).toBe("https://example.com/v1");
  });
});
