/**
 * 環境変数の読み込みと検証
 * 起動時に必須変数を検証し、欠落していれば明確なエラーで失敗させる。
 * Bun では Hono の c.env から環境変数を取得できないため、process.env を使う。
 */

export interface Config {
  /** OpenAI API キー（必須） */
  openaiApiKey: string;
  /** 使用するモデル（既定: gpt-4o-mini） */
  openaiModel: string;
  /** OpenAI 互換エンドポイントの base URL（任意、未設定なら undefined） */
  openaiBaseUrl: string | undefined;
  /** ナレッジベース Django REST API の base URL（必須） */
  kbApiBaseUrl: string;
  /**
   * 検索結果を採用するコサイン距離の上限（小さいほど厳しい）。
   * これより大きい（＝関連が薄い）チャンクは破棄する。既定 1.0。
   */
  searchMaxDistance: number;
}

/** 環境変数ソースの型（process.env 互換） */
type EnvSource = Record<string, string | undefined>;

/**
 * 環境変数から設定を構築する。
 * 前提条件: KB_API_BASE_URL が設定されていること。requireOpenAI=true（既定）の場合は OPENAI_API_KEY も必須。
 * 事後条件: 検証済みの Config を返す。欠落時は Error を投げる
 */
export function loadConfig(
  env: EnvSource = process.env,
  opts: { requireOpenAI?: boolean } = {},
): Config {
  const { requireOpenAI = true } = opts;
  const openaiApiKey = env.OPENAI_API_KEY?.trim();
  const kbApiBaseUrl = env.KB_API_BASE_URL?.trim();

  const missing: string[] = [];
  if (requireOpenAI && !openaiApiKey) missing.push("OPENAI_API_KEY");
  if (!kbApiBaseUrl) missing.push("KB_API_BASE_URL");
  if (missing.length > 0) {
    throw new Error(
      `必須の環境変数が未設定です: ${missing.join(", ")}`,
    );
  }

  const openaiBaseUrl = env.OPENAI_BASE_URL?.trim();

  // 検索距離閾値（不正値は既定 1.0 にフォールバック）
  const rawDistance = env.SEARCH_MAX_DISTANCE?.trim();
  const parsedDistance = rawDistance ? Number(rawDistance) : 1.0;
  const searchMaxDistance = Number.isFinite(parsedDistance)
    ? parsedDistance
    : 1.0;

  return {
    // 上の検証で undefined でないことが保証されている
    openaiApiKey: openaiApiKey as string,
    openaiModel: env.OPENAI_MODEL?.trim() || "gpt-4o-mini",
    openaiBaseUrl: openaiBaseUrl ? openaiBaseUrl : undefined,
    kbApiBaseUrl: kbApiBaseUrl as string,
    searchMaxDistance,
  };
}
