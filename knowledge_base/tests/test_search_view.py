"""
SearchView のテスト
テスト対象：kb/views.py (SearchView)、kb/forms.py (SearchForm)、kb/urls.py
embedder と searcher はモックして実モデルロードを回避する
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse


def _make_chunk(content: str, filename: str):
    """テスト用の Chunk オブジェクトを生成するヘルパー（DB 保存なし）
    SimpleNamespace を使い content / document.filename を自由に設定できる
    """
    doc = SimpleNamespace(filename=filename)
    return SimpleNamespace(content=content, document=doc)


class SearchViewGetTest(TestCase):
    """GET /search/ のテスト"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:search")

    def test_get_returns_200(self):
        """GET /search/ は HTTP 200 を返す"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_renders_search_template(self):
        """GET /search/ は kb/search.html テンプレートを使用する"""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "kb/search.html")
        # テンプレート継承により kb/base.html も使用されること
        self.assertTemplateUsed(response, "kb/base.html")

    def test_get_contains_empty_form(self):
        """GET /search/ のレスポンスには空のフォームが含まれる"""
        response = self.client.get(self.url)
        self.assertIn("form", response.context)
        self.assertFalse(response.context["form"].is_bound)

    def test_get_no_chunks_in_context(self):
        """GET /search/ のコンテキストには chunks が含まれない（None または空）"""
        response = self.client.get(self.url)
        chunks = response.context.get("chunks")
        self.assertIsNone(chunks)


class SearchViewPostInvalidTest(TestCase):
    """空クエリ POST のテスト（バリデーションエラー）"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:search")

    def test_post_empty_query_returns_200(self):
        """空クエリの POST は HTTP 200 を返す"""
        response = self.client.post(self.url, {"query": ""})
        self.assertEqual(response.status_code, 200)

    def test_post_empty_query_contains_validation_error(self):
        """空クエリの POST はバリデーションエラーテキストを含む"""
        response = self.client.post(self.url, {"query": ""})
        content = response.content.decode("utf-8")
        self.assertIn("検索クエリを入力してください", content)

    def test_post_empty_query_htmx_renders_partial(self):
        """HX-Request ヘッダー付き空クエリ POST は search_results.html パーシャルを使用する"""
        response = self.client.post(
            self.url,
            {"query": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "kb/partials/search_results.html")
        # パーシャルなので <html> タグは含まれないこと
        content = response.content.decode("utf-8")
        self.assertNotIn("<html", content)

    def test_post_empty_query_regular_renders_full_page(self):
        """通常の空クエリ POST は search.html フルページを使用する"""
        response = self.client.post(self.url, {"query": ""})
        self.assertTemplateUsed(response, "kb/search.html")


class SearchViewPostValidTest(TestCase):
    """有効なクエリ POST のテスト"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:search")

    @patch("kb.views.searcher")
    @patch("kb.views.embedder")
    def test_post_valid_query_returns_200(self, mock_embedder, mock_searcher):
        """有効なクエリの POST は HTTP 200 を返す"""
        mock_embedder.embed_one.return_value = [0.1] * 384
        mock_searcher.search.return_value = []

        response = self.client.post(self.url, {"query": "Python とは"})
        self.assertEqual(response.status_code, 200)

    @patch("kb.views.searcher")
    @patch("kb.views.embedder")
    def test_post_valid_query_calls_embed_one(self, mock_embedder, mock_searcher):
        """有効なクエリの POST は embedder.embed_one を呼び出す"""
        mock_embedder.embed_one.return_value = [0.1] * 384
        mock_searcher.search.return_value = []

        self.client.post(self.url, {"query": "Python とは"})

        mock_embedder.embed_one.assert_called_once_with("Python とは")

    @patch("kb.views.searcher")
    @patch("kb.views.embedder")
    def test_post_valid_query_calls_search(self, mock_embedder, mock_searcher):
        """有効なクエリの POST は searcher.search を呼び出す"""
        vector = [0.1] * 384
        mock_embedder.embed_one.return_value = vector
        mock_searcher.search.return_value = []

        self.client.post(self.url, {"query": "Python とは"})

        mock_searcher.search.assert_called_once_with(vector)

    @patch("kb.views.searcher")
    @patch("kb.views.embedder")
    def test_post_valid_query_regular_renders_full_page(
        self, mock_embedder, mock_searcher
    ):
        """通常の有効クエリ POST は search.html フルページを使用する"""
        mock_embedder.embed_one.return_value = [0.1] * 384
        mock_searcher.search.return_value = [_make_chunk("内容", "test.pdf")]

        response = self.client.post(self.url, {"query": "Python とは"})

        self.assertTemplateUsed(response, "kb/search.html")
        self.assertTemplateUsed(response, "kb/partials/search_results.html")

    @patch("kb.views.searcher")
    @patch("kb.views.embedder")
    def test_post_valid_query_htmx_renders_partial_only(
        self, mock_embedder, mock_searcher
    ):
        """HX-Request ヘッダー付き有効クエリ POST は search_results.html パーシャルのみを使用する"""
        mock_embedder.embed_one.return_value = [0.1] * 384
        mock_searcher.search.return_value = [_make_chunk("内容", "test.pdf")]

        response = self.client.post(
            self.url,
            {"query": "Python とは"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        # パーシャルなので <html> タグは含まれないこと
        content = response.content.decode("utf-8")
        self.assertNotIn("<html", content)
        self.assertTemplateUsed(response, "kb/partials/search_results.html")

    @patch("kb.views.searcher")
    @patch("kb.views.embedder")
    def test_post_valid_query_htmx_contains_results(
        self, mock_embedder, mock_searcher
    ):
        """HX-Request 付き POST はチャンク内容をレスポンスに含む"""
        mock_embedder.embed_one.return_value = [0.1] * 384
        chunk = _make_chunk("Python は汎用プログラミング言語です", "python_guide.pdf")
        mock_searcher.search.return_value = [chunk]

        response = self.client.post(
            self.url,
            {"query": "Python とは"},
            HTTP_HX_REQUEST="true",
        )

        content = response.content.decode("utf-8")
        self.assertIn("Python は汎用プログラミング言語です", content)
        self.assertIn("python_guide.pdf", content)

    @patch("kb.views.searcher")
    @patch("kb.views.embedder")
    def test_post_valid_query_empty_results_shows_no_docs_message(
        self, mock_embedder, mock_searcher
    ):
        """チャンクが0件の場合は「暂无可搜索的文档」メッセージを表示する"""
        mock_embedder.embed_one.return_value = [0.1] * 384
        mock_searcher.search.return_value = []

        response = self.client.post(self.url, {"query": "存在しないトピック"})

        content = response.content.decode("utf-8")
        self.assertIn("暂无可搜索的文档", content)
