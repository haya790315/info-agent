/**
 * AgentLoop: LLM と工具の Function Calling 往復ループを駆動する。
 * - 会話履歴を取得し、[system]+history+[user] でループ
 * - tool_calls があれば実行して role:"tool" で回灌、無ければ最終回答
 * - MAX_TOOL_ROUNDS 到達時はツール無効で最終呼び出しし文字答案を強制（空回答を返さない）
 * - 実際の検索結果から出典ブロックを確定的に付加（モデル出力に依存しない）
 * - ツール呼び出しの名前/引数/結果サマリを console に出力
 */
import { LLMError, type LLMClient } from "./llm";
import type { SessionStore } from "./session";
import type {
  AssistantTurn,
  ChatMessage,
  ErasedToolDefinition,
  LLMToolSpec,
  SearchResultItem,
  ToolCall,
  ToolResult,
} from "./types";

export interface AgentReply {
  answer: string;
}

export interface AgentService {
  run(sessionId: string, userMessage: string): Promise<AgentReply>;
}

const SYSTEM_PROMPT = [
  "あなたは社内 ナレッジベースのアシスタントです。\n",
  "ナレッジベースの情報を最優先しますが、それに限らず一般的な知識でも質問に答えてかまいません。\n",
  "\n",
  "【ナレッジベースの優先利用】\n",
  "文書・社内資料の内容に関わりそうな質問には、まず search_knowledge_base で本文を取得してから回答してください。\n",
  "\n",
  "【固有名詞（人名・会社名・ファイル名）の検索戦略】\n",
  "人名・会社名・製品名などの固有名詞について『〇〇を知っているか』『〇〇の資料はあるか』と聞かれた場合、\n",
  "その固有名詞は文書の本文に含まれず、ファイル名にしか存在しないことがよくあります（例: 履歴書・職歴書の氏名）。\n",
  "この場合、search_knowledge_base だけに頼ると見つからないことがあるため、必ず list_documents でファイル名一覧を確認してください。\n",
  "一致または部分一致するファイルがあれば、その固有名詞の資料は存在します。続けてその種別（category）や関連語で search_knowledge_base を行い、本文を取得して回答してください。\n",
  "\n",
  "【多言語・同義語検索戦略】\n",
  "ユーザーが英語で質問しても、文書内は日本語で書かれている場合があります（逆も同様）。\n",
  "質問に含まれる概念を英語・日本語・略語・同義語に展開し、異なるクエリで複数回検索してください。\n",
  "【再検索ルール】\n",
  "最初の検索で結果が空・または質問と無関係だった場合は、別の言語・別のキーワードで必ず再検索してください。\n",
  "諦める前に少なくとも 3 種類の異なるクエリを試すこと。\n",
  "\n",
  "【ナレッジベースに無い場合の対応】\n",
  "3 種類以上のクエリを試しても該当資料が見つからない、または明らかに一般的な質問（資料に依存しない知識）の場合は、\n",
  "あなた自身の一般知識を用いて回答してかまいません。\n",
  "その際は『※これはナレッジベースの資料ではなく、一般的な知識に基づく回答です』のように、根拠が資料でないことを明示してください。\n",
  "ナレッジベースの情報と一般知識を組み合わせて答える場合は、どこまでが資料に基づくかを区別して示してください。\n",
  "\n",
  "【推測の禁止（最重要）】\n",
  "確信が持てない事実、特に固有名詞・数値・日付・社内固有の情報は、決して創作・推測してはいけません。\n",
  "本当に分からない場合は、無理に答えず『分かりません』『確実な情報がありません』と正直に述べてください。\n",
  "get_document_detail はメタ情報（状態・チャンク数）のみを返すため、そこから文書の内容を推測・創作してはいけません。\n",
  "ナレッジベースに基づいて答える場合は、検索で得たチャンクのうち質問に実際に関連する内容だけを根拠にし、無関係なチャンクは無視してください。\n",
].join("");

const LLM_ERROR_REPLY =
  "申し訳ありません。ただいま回答を生成できません。しばらくしてから再度お試しください。";
const EMPTY_ANSWER_FALLBACK = "申し訳ありません、回答をまとめられませんでした。";
// 出典に採用する上位チャンク数（末尾の低関連チャンクによるノイズを抑える）
const MAX_SOURCE_CHUNKS = 3;

export interface AgentDeps {
  llm: LLMClient;
  registry: ErasedToolDefinition[];
  session: SessionStore;
  /** 工具呼び出しループの上限（既定 5） */
  maxToolRounds?: number;
  /** ログ出力先（既定 console、テストで差し替え可能） */
  logger?: Pick<Console, "log">;
}

export function createAgentLoop(deps: AgentDeps): AgentService {
  const { llm, registry, session } = deps;
  // 多言語再検索（3クエリ×往復）を許容するため余裕を持たせる
  const maxToolRounds = deps.maxToolRounds ?? 8;
  const logger = deps.logger ?? console;

  const toolSpecs: LLMToolSpec[] = registry.map((t) => ({
    name: t.name,
    description: t.description,
    jsonSchema: t.jsonSchema,
  }));

  async function runToolCall(tc: ToolCall): Promise<ToolResult> {
    const tool = registry.find((t) => t.name === tc.name);
    if (!tool) {
      return { ok: false, error: `未知のツール: ${tc.name}` };
    }
    let args: unknown = {};
    try {
      args = JSON.parse(tc.argumentsJson || "{}");
    } catch {
      args = {};
    }
    return tool.execute(args);
  }

  function buildSourceBlock(sources: SearchResultItem[]): string {
    // 検索は常に top-5 を返し関連度の閾値が無いため、末尾（低関連）チャンクが
    // 無関係な文書を出典に混ぜてしまう。最上位チャンクのみを採用してノイズを抑える。
    const topChunks = sources.slice(0, MAX_SOURCE_CHUNKS);
    const seen = new Set<string>();
    const lines: string[] = [];
    for (const s of topChunks) {
      const key = `${s.filename}|${s.fileUrl ?? ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      lines.push(s.fileUrl ? `- ${s.filename}（${s.fileUrl}）` : `- ${s.filename}`);
    }
    return lines.length > 0 ? `\n\n出典:\n${lines.join("\n")}` : "";
  }

  return {
    async run(sessionId: string, userMessage: string): Promise<AgentReply> {
      const working: ChatMessage[] = [
        { role: "system", content: SYSTEM_PROMPT },
        ...session.getHistory(sessionId),
        { role: "user", content: userMessage },
      ];
      const sources: SearchResultItem[] = [];
      let answer: string | null = null;

      try {
        for (let round = 0; round < maxToolRounds; round++) {
          const turn: AssistantTurn = await llm.chat(working, toolSpecs);
          if (turn.toolCalls.length === 0) {
            answer = turn.content;
            break;
          }
          working.push({
            role: "assistant",
            content: turn.content,
            toolCalls: turn.toolCalls,
          });
          for (const tc of turn.toolCalls) {
            logger.log(`[tool-call] ${tc.name} args=${tc.argumentsJson}`);
            const result = await runToolCall(tc);
            if (tc.name === "search_knowledge_base" && result.ok) {
              sources.push(...(result.data as SearchResultItem[]));
            }
            const summary = result.ok
              ? `ok size=${JSON.stringify(result.data).length}`
              : `error=${result.error}`;
            logger.log(`[tool-result] ${tc.name} ${summary}`);
            working.push({
              role: "tool",
              toolCallId: tc.id,
              content: JSON.stringify(
                result.ok ? result.data : { error: result.error },
              ),
            });
          }
        }

        // 上限到達などで最終回答が未確定なら、ツール無効で文字答案を強制する
        if (answer === null) {
          const finalTurn = await llm.chat(working, []);
          answer = finalTurn.content;
        }
      } catch (err) {
        if (err instanceof LLMError) {
          return { answer: LLM_ERROR_REPLY };
        }
        throw err;
      }

      const baseAnswer =
        answer && answer.trim().length > 0 ? answer : EMPTY_ANSWER_FALLBACK;
      const withSources = baseAnswer + buildSourceBlock(sources);

      session.append(
        sessionId,
        { role: "user", content: userMessage },
        { role: "assistant", content: withSources },
      );
      return { answer: withSources };
    },
  };
}
