"""
UploadView のテスト
テスト対象：kb/views.py (UploadView)、kb/forms.py (UploadForm)、kb/urls.py
"""
import io
from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
from django.test import Client, TestCase
from django.urls import reverse


def _make_pdf_bytes(text: str = "Hello World") -> bytes:
    """テスト用の最小 PDF バイト列を生成するヘルパー"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_pdf_file(text: str = "Hello World", name: str = "test.pdf"):
    """テスト用の PDF ファイルオブジェクトを生成するヘルパー"""
    pdf_bytes = _make_pdf_bytes(text)
    return io.BytesIO(pdf_bytes), name


class UploadViewGetTest(TestCase):
    """GET /upload/ のテスト"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def test_get_returns_200(self):
        """GET /upload/ は HTTP 200 を返す"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_renders_upload_template(self):
        """GET /upload/ は kb/upload.html テンプレートを使用する"""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "kb/upload.html")
        # テンプレート継承により kb/base.html も使用されること
        self.assertTemplateUsed(response, "kb/base.html")

    def test_get_contains_form(self):
        """GET /upload/ のレスポンスにはフォームが含まれる"""
        response = self.client.get(self.url)
        self.assertIn("form", response.context)


class UploadViewPostNonPdfTest(TestCase):
    """非 PDF ファイル POST のテスト"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def test_post_non_pdf_returns_200(self):
        """非 PDF ファイルの POST は HTTP 200 を返す（フォームエラーで再表示）"""
        txt_file = io.BytesIO(b"This is a text file")
        txt_file.name = "test.txt"
        # Django テストクライアントは content_type を省略することで
        # multipart/form-data として自動エンコードする
        response = self.client.post(
            self.url,
            {"pdf_file": txt_file},
        )
        self.assertEqual(response.status_code, 200)

    def test_post_non_pdf_contains_error_message(self):
        """非 PDF ファイルの POST はエラーメッセージを含む"""
        txt_file = io.BytesIO(b"This is a text file")
        txt_file.name = "test.txt"
        response = self.client.post(
            self.url,
            {"pdf_file": txt_file},
        )
        self.assertEqual(response.status_code, 200)
        # レスポンス内容にエラーテキストが含まれていること
        content = response.content.decode("utf-8")
        # フォームエラーがレスポンスに含まれること
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)


class UploadViewPostEmptyFileTest(TestCase):
    """空ファイル POST のテスト"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def test_post_empty_file_returns_200(self):
        """空ファイルの POST は HTTP 200 を返す（フォームエラーで再表示）"""
        empty_file = io.BytesIO(b"")
        empty_file.name = "empty.pdf"
        response = self.client.post(
            self.url,
            {"pdf_file": empty_file},
        )
        self.assertEqual(response.status_code, 200)

    def test_post_empty_file_has_form_errors(self):
        """空ファイルの POST はフォームエラーを含む"""
        empty_file = io.BytesIO(b"")
        empty_file.name = "empty.pdf"
        response = self.client.post(
            self.url,
            {"pdf_file": empty_file},
        )
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)


class UploadViewPostLargeFileTest(TestCase):
    """10MB 超えファイル POST のテスト"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def test_post_file_over_10mb_returns_200(self):
        """10MB 超えファイルの POST は HTTP 200 を返す（フォームエラーで再表示）"""
        # 10MB + 1 バイトのダミーデータ（PDF ヘッダーを持つ）
        # content_type を合わせるために PDF ヘッダーを付ける
        large_content = b"%PDF-1.4\n" + b"x" * (10 * 1024 * 1024 + 1)
        large_file = io.BytesIO(large_content)
        large_file.name = "large.pdf"
        response = self.client.post(
            self.url,
            {"pdf_file": large_file},
        )
        self.assertEqual(response.status_code, 200)

    def test_post_file_over_10mb_has_form_errors(self):
        """10MB 超えファイルの POST はフォームエラーを含む"""
        large_content = b"%PDF-1.4\n" + b"x" * (10 * 1024 * 1024 + 1)
        large_file = io.BytesIO(large_content)
        large_file.name = "large.pdf"
        response = self.client.post(
            self.url,
            {"pdf_file": large_file},
        )
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)


class UploadViewPostValidPdfTest(TestCase):
    """有効な PDF POST のテスト"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    @patch("kb.views.embedder")
    @patch("kb.views.processor")
    def test_post_valid_pdf_calls_extract_text(self, mock_processor, mock_embedder):
        """有効な PDF の POST は processor.extract_text を呼び出す"""
        # processor.extract_text が有効なテキストを返すようにモック
        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        pdf_bytes = _make_pdf_bytes("Sample text content")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "valid.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        mock_processor.extract_text.assert_called_once()

    @patch("kb.views.embedder")
    @patch("kb.views.processor")
    def test_post_valid_pdf_calls_embed_many(self, mock_processor, mock_embedder):
        """有効な PDF の POST は embedder.embed_many を呼び出す"""
        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        pdf_bytes = _make_pdf_bytes("Sample text content")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "valid.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        mock_embedder.embed_many.assert_called_once_with(["Sample text content"])

    @patch("kb.views.embedder")
    @patch("kb.views.processor")
    def test_post_valid_pdf_redirects_to_document_detail(
        self, mock_processor, mock_embedder
    ):
        """有効な PDF の POST は /documents/{id}/ にリダイレクトする"""
        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        pdf_bytes = _make_pdf_bytes("Sample text content")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "valid.pdf"

        response = self.client.post(self.url, {"pdf_file": pdf_file})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/documents/", response["Location"])

    @patch("kb.views.embedder")
    @patch("kb.views.processor")
    def test_post_pdf_with_empty_text_sets_status_failed(
        self, mock_processor, mock_embedder
    ):
        """テキストが空の PDF の POST は Document.status を failed に設定する"""
        # extract_text が空文字列を返すようにモック（画像型 PDF を模倣）
        mock_processor.extract_text.return_value = "   "  # 空白のみ（strip() で空になる）
        mock_embedder.embed_many.return_value = []

        pdf_bytes = _make_pdf_bytes("Hello")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "image_only.pdf"

        response = self.client.post(self.url, {"pdf_file": pdf_file})

        # リダイレクトされること
        self.assertEqual(response.status_code, 302)

        # Document が failed ステータスで保存されていること
        from knowledge_base.models import Document
        doc = Document.objects.last()
        self.assertEqual(doc.status, Document.STATUS_FAILED)
