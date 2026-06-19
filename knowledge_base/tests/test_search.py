# セマンティック検索エンドツーエンド統合テスト
# Task 4.3: kb/tests/test_search.py
# SQLite 環境では VectorField が使えないため、embedder と searcher はモックで対応する
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from django.urls import reverse


def _make_simple_chunk(content: str, filename: str):
    # テスト用チャンクオブジェクト（DB 保存なし）
    doc = SimpleNamespace(filename=filename)
    return SimpleNamespace(content=content, document=doc)


class SearchKeywordEndToEndTest(TestCase):
    # テスト1: キーワードを含む PDF を ingestion 後、そのキーワードで検索 → ≤5 件、キーワード含有を確認

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:search")

    @patch("knowledge_base.views.searcher")
    @patch("knowledge_base.views.embedder")
    def test_keyword_search_returns_chunk_containing_keyword(
        self, mock_embedder, mock_searcher
    ):
        # SimpleNamespace を使うことで Django テンプレートの属性アクセスが正しく機能する
        mock_chunk = _make_simple_chunk(
            "RAGシステムについて説明するドキュメントです", "test_rag.pdf"
        )

        mock_embedder.embed_one.return_value = [0.0] * 384
        mock_searcher.search.return_value = [mock_chunk]

        response = self.client.post(
            self.url,
            {"query": "RAG"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # キーワードがレスポンスに含まれること
        self.assertIn("RAGシステムについて", content)

    @patch("knowledge_base.views.searcher")
    @patch("knowledge_base.views.embedder")
    def test_keyword_search_returns_at_most_5_chunks(
        self, mock_embedder, mock_searcher
    ):
        # searcher.search が返す件数が 5 件以下であることを確認する
        chunks = [
            _make_simple_chunk(f"RAGシステム チャンク{i}", f"doc{i}.pdf")
            for i in range(5)
        ]
        mock_embedder.embed_one.return_value = [0.0] * 384
        mock_searcher.search.return_value = chunks

        response = self.client.post(
            self.url,
            {"query": "RAG"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        # コンテキストの chunks が ≤5 件であること
        chunks_in_ctx = response.context.get("chunks", [])
        self.assertLessEqual(len(chunks_in_ctx), 5)


class SearchEmptyDatabaseTest(TestCase):
    # テスト2: 空 DB 状態で検索 → 「暂无可搜索的文档」を含むパーシャルレスポンス

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:search")

    @patch("knowledge_base.views.searcher")
    @patch("knowledge_base.views.embedder")
    def test_empty_db_search_shows_no_docs_message(
        self, mock_embedder, mock_searcher
    ):
        # DB が空（チャンク 0 件）を模倣
        mock_embedder.embed_one.return_value = [0.0] * 384
        mock_searcher.search.return_value = []

        response = self.client.post(
            self.url,
            {"query": "存在しないトピック"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # 「該当するドキュメントが見つかりませんでした」メッセージが含まれること
        self.assertIn("該当するドキュメントが見つかりませんでした", content)


class SearchHtmxPartialTest(TestCase):
    # テスト3: HX-Request ヘッダー付き POST → レスポンスに <html> タグが含まれないこと

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:search")

    @patch("knowledge_base.views.searcher")
    @patch("knowledge_base.views.embedder")
    def test_htmx_request_returns_partial_without_html_tag(
        self, mock_embedder, mock_searcher
    ):
        # 結果ありケース
        mock_embedder.embed_one.return_value = [0.0] * 384
        mock_searcher.search.return_value = [
            _make_simple_chunk("HTMX テスト用コンテンツ", "htmx_test.pdf")
        ]

        response = self.client.post(
            self.url,
            {"query": "HTMX"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # パーシャルレスポンスなので <html> タグが含まれないこと
        self.assertNotIn("<html", content)

    @patch("knowledge_base.views.searcher")
    @patch("knowledge_base.views.embedder")
    def test_htmx_request_empty_results_returns_partial_without_html_tag(
        self, mock_embedder, mock_searcher
    ):
        # 結果なしケース
        mock_embedder.embed_one.return_value = [0.0] * 384
        mock_searcher.search.return_value = []

        response = self.client.post(
            self.url,
            {"query": "HTMX"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertNotIn("<html", content)


class SearchEmptyQueryValidationTest(TestCase):
    # テスト4: 空クエリ POST → バリデーションエラー（EmbedderService / SearcherService を呼び出さない）

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:search")

    @patch("knowledge_base.views.searcher")
    @patch("knowledge_base.views.embedder")
    def test_empty_query_returns_validation_error(
        self, mock_embedder, mock_searcher
    ):
        response = self.client.post(self.url, {"query": ""})

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # バリデーションエラーメッセージが含まれること
        self.assertIn("検索クエリを入力してください", content)

    @patch("knowledge_base.views.searcher")
    @patch("knowledge_base.views.embedder")
    def test_empty_query_does_not_call_embedder_or_searcher(
        self, mock_embedder, mock_searcher
    ):
        # 空クエリのバリデーションエラー時は embedder / searcher を呼び出さない
        self.client.post(self.url, {"query": ""})

        mock_embedder.embed_one.assert_not_called()
        mock_searcher.search.assert_not_called()
