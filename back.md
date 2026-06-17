Skip navigation
Search
技術課題（AIエージェント / MCP Apps）
概要
RAYVENのエンジニア採用における技術選考のうち、パターンA（持ち帰り課題）の内容です。

以下2つのテーマからいずれか1つを選択し、小規模なアプリケーションを実装してください。

テーマA: AI APIを使ったAIエージェント開発

テーマB: MCP Appsの作成

本課題で作成するエージェント / MCP Appsは、実際に業務で活用できる実用性を持つことを前提とします。 技術デモや学習用の題材ではなく、社内外の具体的な業務課題を解決する実装を求めます。

未経験の方へ 本課題は「完璧な実装」より「動くものを作ってみて、そこから何を学んだか」を重視します。わからないことは積極的にClaude Code等のAIツールや担当者にご相談ください。小さくても動くものを目指しましょう。

課題の目的
TypeScriptの実装力を確認する

AI API（LLM API）を直接使ったエージェント実装力を確認する

新技術へのキャッチアップ力を確認する

ドキュメント化・属人化解消への意識を確認する

実業務に活かせる題材選定・ビジネスセンスを確認する

期間
課題提示から1週間（延長相談可）

想定稼働時間：合計10〜15時間程度

テーマA: AI APIを使ったAIエージェント開発
任意のAI API（LLM API）を直接呼び出すエージェントアプリケーションを自作してください。自前でAPIを叩きツール呼び出し（Function Calling / Tool Use）ループを実装することが本テーマの中心です。

ツール群の実装方法は自由です。MCP（Model Context Protocol）を活用してもOK（既存のMCPサーバーを接続する／自前でMCPサーバーを実装する）、単純な関数・クラス・外部API呼び出し等で実装するのもOKです。

利用可能なAI API
任意のLLM API（Anthropic Claude / OpenAI / Google Gemini など）を自由に選択してください。

アーキテクチャ例






エージェント本体: 任意のLLM SDKを使用し、Function Calling / Tool Useループを自前実装

ツール群: 実装形態自由（関数・モジュール・MCPサーバー・外部API等。既存MCPサーバーの活用も可）

UI: 自由選択（CLI / Web / Slack Bot / Discord Bot / Desktop / 何でも可）

必須要件
TypeScriptで実装

任意のLLM を使ったエージェント本体の実装

UIは自由選択（CLI / Web / Chat Bot / Desktop等、何でも可）

エンドツーエンドで動作する状態で提出

選定したAI API・アーキテクチャとその選定理由をREADMEに明記

歓迎要件
MCP（Model Context Protocol）サーバーの自前実装

RAG（Retrieval-Augmented Generation）の活用（ベクトル検索・埋め込みを用いた外部知識の参照など）

ファインチューニングの活用(特定タスクに最適化したモデルの利用)

エージェントの思考プロセスのログ出力・可視化

エラーハンドリング・リトライ戦略

テーマB: MCP Apps作成
ChatGPTやClaudeなどのチャットUIに組み込まれ、ユーザーがチャット画面からアプリのUIを呼び出して操作できるアプリケーションを作成してください。MCP（Model Context Protocol）を介してチャットUIと連携させます。

対象プラットフォーム（いずれか、または両対応）
Apps in ChatGPT（ChatGPT Apps）

OpenAI Apps SDK ドキュメント: https://developers.openai.com/apps-sdk

発表記事: https://openai.com/index/introducing-apps-in-chatgpt/

Apps in Claude（MCP Apps拡張）

MCP Apps ドキュメント: https://modelcontextprotocol.io/docs/extensions/apps

発表ブログ: https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/

サンプルリポジトリ: https://github.com/modelcontextprotocol/ext-apps

どちらのプラットフォーム向けに実装しても構いません。選定したプラットフォームと選定理由をREADMEに明記してください。

要件
TypeScriptで実装

MCP Apps仕様に沿ったChatGPT / Claude連携

歓迎要件
データ永続化（SQLite / Neon / Cloudflare D1 等、何でも可）

最低限のCI（GitHub Actionsでlint/typecheck）

共通要件
必須
GitHubリポジトリとして提出（public or private共有）

README.mdの整備

セットアップ手順（APIキーの設定方法含む）

アーキテクチャ図 / 構成説明

設計意図

使い方

想定ユーザー・業務シナリオ（誰が・いつ・どの業務で使うか）

歓迎
TypeScriptを使った実装

ホスティング（デプロイ済み動作環境URL）

ランタイム・フレームワーク
言語: TypeScript（必須）

ランタイム: 自由選択（Node.js / Bun / Deno いずれも可）

参考までに、RAYVEN社内では Bun を標準採用しています。

フレームワーク: 自由選択（Hono / Express / Fastify / Elysia など、お好きなものをお使いください）

進め方・注意事項
使用ツールは自由: Claude Code / Cursor / Copilot など、AI駆動開発ツールの使用を推奨・歓迎します

API利用料金: 本課題で発生するLLM API等の利用料金は候補者ご自身のご負担となります（無料枠の範囲内でも実装可能です）

コードの公開範囲: GitHubリポジトリは public / private どちらでも構いません。private の場合は別途アクセス権をお渡しください

機密情報の扱い: 題材として業務課題を扱う場合、所属組織の機密情報・個人情報を含めないようご注意ください

成果物の扱い: 成果物の著作権は候補者に帰属します。RAYVEN側で社内の参考資料として活用させていただく場合がありますので、あらかじめご了承ください

質問・相談: 課題を進める中で不明点・相談があれば、いつでも担当者（鈴山）までご連絡ください

提出方法
以下2点を担当者（鈴山）宛に送付してください。

GitHubリポジトリURLの共有

30分程度のデモ実施（Google Meet で実施します）

作成したアプリケーション / MCP Appsのデモ

設計意図・工夫した点・詰まった点とその解決プロセスの説明

Claude Codeの活用方法

実務投入するならどう改善・拡張するか

デモの日程は、GitHubリポジトリ共有後に調整させていただきます。

連絡先
担当者: 鈴山英寿（s.hidehisa@rayven.cloud）

質問・相談はメールまたは共有済みのSlackチャンネルまでお気軽にどうぞ



【社内用】エンジニア技術課題 評価観点（AIエージェント / MCP Apps開発）
 Outline
技術課題（AIエージェント / MCP Apps）
概要
RAYVENのエンジニア採用における技術選考のうち、パターンA（持ち帰り課題）の内容です。

以下2つのテーマからいずれか1つを選択し、小規模なアプリケーションを実装してください。

テーマA: AI APIを使ったAIエージェント開発

テーマB: MCP Appsの作成

本課題で作成するエージェント / MCP Appsは、実際に業務で活用できる実用性を持つことを前提とします。 技術デモや学習用の題材ではなく、社内外の具体的な業務課題を解決する実装を求めます。

未経験の方へ 本課題は「完璧な実装」より「動くものを作ってみて、そこから何を学んだか」を重視します。わからないことは積極的にClaude Code等のAIツールや担当者にご相談ください。小さくても動くものを目指しましょう。

課題の目的
TypeScriptの実装力を確認する

AI API（LLM API）を直接使ったエージェント実装力を確認する

新技術へのキャッチアップ力を確認する

ドキュメント化・属人化解消への意識を確認する

実業務に活かせる題材選定・ビジネスセンスを確認する

期間
課題提示から1週間（延長相談可）

想定稼働時間：合計10〜15時間程度

テーマA: AI APIを使ったAIエージェント開発
任意のAI API（LLM API）を直接呼び出すエージェントアプリケーションを自作してください。自前でAPIを叩きツール呼び出し（Function Calling / Tool Use）ループを実装することが本テーマの中心です。

ツール群の実装方法は自由です。MCP（Model Context Protocol）を活用してもOK（既存のMCPサーバーを接続する／自前でMCPサーバーを実装する）、単純な関数・クラス・外部API呼び出し等で実装するのもOKです。

利用可能なAI API
任意のLLM API（Anthropic Claude / OpenAI / Google Gemini など）を自由に選択してください。

アーキテクチャ例
flowchart TD
    User([ユーザー])
    UI[UI<br/>CLI / Web / Slack Bot / Desktop 等]
    Agent[エージェント本体<br/>任意のLLM SDK]
    Tools[ツール群<br/>関数 / MCPサーバー / 外部API 等]
    Resources[(外部API / DB / ファイル 等)]

    User <--> UI
    UI <--> Agent
    Agent <-->|Function Calling / Tool Use ループ| Tools
    Tools <--> Resources
エージェント本体: 任意のLLM SDKを使用し、Function Calling / Tool Useループを自前実装

ツール群: 実装形態自由（関数・モジュール・MCPサーバー・外部API等。既存MCPサーバーの活用も可）

UI: 自由選択（CLI / Web / Slack Bot / Discord Bot / Desktop / 何でも可）

必須要件
TypeScriptで実装

任意のLLM を使ったエージェント本体の実装

UIは自由選択（CLI / Web / Chat Bot / Desktop等、何でも可）

エンドツーエンドで動作する状態で提出

選定したAI API・アーキテクチャとその選定理由をREADMEに明記

歓迎要件
MCP（Model Context Protocol）サーバーの自前実装

RAG（Retrieval-Augmented Generation）の活用（ベクトル検索・埋め込みを用いた外部知識の参照など）

ファインチューニングの活用(特定タスクに最適化したモデルの利用)

エージェントの思考プロセスのログ出力・可視化

エラーハンドリング・リトライ戦略

テーマB: MCP Apps作成
ChatGPTやClaudeなどのチャットUIに組み込まれ、ユーザーがチャット画面からアプリのUIを呼び出して操作できるアプリケーションを作成してください。MCP（Model Context Protocol）を介してチャットUIと連携させます。

対象プラットフォーム（いずれか、または両対応）
Apps in ChatGPT（ChatGPT Apps）

OpenAI Apps SDK ドキュメント: https://developers.openai.com/apps-sdk

発表記事: https://openai.com/index/introducing-apps-in-chatgpt/

Apps in Claude（MCP Apps拡張）

MCP Apps ドキュメント: https://modelcontextprotocol.io/docs/extensions/apps

発表ブログ: https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/

サンプルリポジトリ: https://github.com/modelcontextprotocol/ext-apps

どちらのプラットフォーム向けに実装しても構いません。選定したプラットフォームと選定理由をREADMEに明記してください。

要件
TypeScriptで実装

MCP Apps仕様に沿ったChatGPT / Claude連携

歓迎要件
データ永続化（SQLite / Neon / Cloudflare D1 等、何でも可）

最低限のCI（GitHub Actionsでlint/typecheck）

共通要件
必須
GitHubリポジトリとして提出（public or private共有）

README.mdの整備

セットアップ手順（APIキーの設定方法含む）

アーキテクチャ図 / 構成説明

設計意図

使い方

想定ユーザー・業務シナリオ（誰が・いつ・どの業務で使うか）

歓迎
TypeScriptを使った実装

ホスティング（デプロイ済み動作環境URL）

ランタイム・フレームワーク
言語: TypeScript（必須）

ランタイム: 自由選択（Node.js / Bun / Deno いずれも可）

参考までに、RAYVEN社内では Bun を標準採用しています。

フレームワーク: 自由選択（Hono / Express / Fastify / Elysia など、お好きなものをお使いください）

進め方・注意事項
使用ツールは自由: Claude Code / Cursor / Copilot など、AI駆動開発ツールの使用を推奨・歓迎します

API利用料金: 本課題で発生するLLM API等の利用料金は候補者ご自身のご負担となります（無料枠の範囲内でも実装可能です）

コードの公開範囲: GitHubリポジトリは public / private どちらでも構いません。private の場合は別途アクセス権をお渡しください

機密情報の扱い: 題材として業務課題を扱う場合、所属組織の機密情報・個人情報を含めないようご注意ください

成果物の扱い: 成果物の著作権は候補者に帰属します。RAYVEN側で社内の参考資料として活用させていただく場合がありますので、あらかじめご了承ください

質問・相談: 課題を進める中で不明点・相談があれば、いつでも担当者（鈴山）までご連絡ください

提出方法
以下2点を担当者（鈴山）宛に送付してください。

GitHubリポジトリURLの共有

30分程度のデモ実施（Google Meet で実施します）

作成したアプリケーション / MCP Appsのデモ

設計意図・工夫した点・詰まった点とその解決プロセスの説明

Claude Codeの活用方法

実務投入するならどう改善・拡張するか

デモの日程は、GitHubリポジトリ共有後に調整させていただきます。

連絡先
担当者: 鈴山英寿（s.hidehisa@rayven.cloud）

質問・相談はメールまたは共有済みのSlackチャンネルまでお気軽にどうぞ



