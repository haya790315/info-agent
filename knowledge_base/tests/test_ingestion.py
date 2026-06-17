"""
ingestion 集成テスト
PDF アップロード → Document/Chunk 保存までの end-to-end フローを検証する
SQLite テスト環境では VectorField が使えないため、Chunk 保存と埋め込み生成はモックで代替する
"""
import io
from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
from django.test import Client, TestCase
from django.urls import reverse

from knowledge_base.models import Document


def _make_pdf_bytes(text: str = "Hello World") -> bytes:
    """テスト用の最小 PDF バイト列を生成するヘルパー"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class IngestionCompleteTest(TestCase):
    """テキスト入り PDF の ingestion が complete になることを検証する"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    @patch("kb.views.Chunk.objects.bulk_create")
    @patch("kb.views.embedder.embed_many")
    def test_text_pdf_sets_status_complete(self, mock_embed_many, mock_bulk_create):
        """テキスト入り PDF をアップロードすると Document.status が complete になる"""
        # 埋め込み生成：ダミーの 384 次元ベクトルを返す
        mock_embed_many.return_value = [[0.1] * 384]
        # Chunk 一括保存：SQLite では VectorField が使えないためモックで代替
        mock_bulk_create.return_value = MagicMock()

        pdf_bytes = _make_pdf_bytes("Hello World ingestion test")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "test_complete.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        # Document が complete ステータスで保存されていること
        doc = Document.objects.last()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.status, Document.STATUS_COMPLETE)

    @patch("kb.views.Chunk.objects.bulk_create")
    @patch("kb.views.embedder.embed_many")
    def test_text_pdf_sets_positive_chunk_count(self, mock_embed_many, mock_bulk_create):
        """テキスト入り PDF のアップロード後、Document.chunk_count が 0 より大きい"""
        # 1 チャンク分のダミーベクトルを返す
        mock_embed_many.return_value = [[0.1] * 384]
        mock_bulk_create.return_value = MagicMock()

        pdf_bytes = _make_pdf_bytes("Hello World ingestion test")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "test_chunk_count.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        # chunk_count が 0 より大きいこと
        doc = Document.objects.last()
        self.assertIsNotNone(doc)
        self.assertGreater(doc.chunk_count, 0)


class IngestionFailedTest(TestCase):
    """テキストなし PDF（画像型 PDF）の ingestion が failed になることを検証する"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    @patch("kb.views.processor.extract_text")
    def test_image_pdf_sets_status_failed(self, mock_extract_text):
        """テキスト抽出が空文字を返す PDF は Document.status が failed になる"""
        # 画像型 PDF を模倣：extract_text が空文字列を返す
        mock_extract_text.return_value = ""

        pdf_bytes = _make_pdf_bytes("dummy")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "image_only.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        # Document が failed ステータスで保存されていること
        doc = Document.objects.last()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.status, Document.STATUS_FAILED)

    @patch("kb.views.processor.extract_text")
    def test_image_pdf_has_non_empty_error_message(self, mock_extract_text):
        """テキスト抽出が空文字を返す PDF は error_message が非空文字列になる"""
        mock_extract_text.return_value = ""

        pdf_bytes = _make_pdf_bytes("dummy")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "image_only_error.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        # error_message が空でないこと
        doc = Document.objects.last()
        self.assertIsNotNone(doc)
        self.assertNotEqual(doc.error_message, "")


class IngestionFormValidationTest(TestCase):
    """フォームバリデーション失敗時の ingestion テスト（DB/サービス呼び出しなし）"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def test_non_pdf_returns_200_with_form_error(self):
        """非 PDF ファイルの POST は HTTP 200 を返し、フォームエラーを含む"""
        txt_file = io.BytesIO(b"This is not a PDF")
        txt_file.name = "test.txt"

        response = self.client.post(self.url, {"pdf_file": txt_file})

        # フォームバリデーション失敗 → 200 で再表示
        self.assertEqual(response.status_code, 200)
        # フォームエラーが含まれること
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)

    def test_empty_file_returns_200_with_form_error(self):
        """0 バイトファイルの POST は HTTP 200 を返し、フォームエラーを含む"""
        empty_file = io.BytesIO(b"")
        empty_file.name = "empty.pdf"

        response = self.client.post(self.url, {"pdf_file": empty_file})

        # フォームバリデーション失敗 → 200 で再表示
        self.assertEqual(response.status_code, 200)
        # フォームエラーが含まれること
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)

    def test_oversized_file_returns_200_with_size_error(self):
        """10MB 超えファイルの POST は HTTP 200 を返し、サイズ制限エラーを含む"""
        # 10MB + 1 バイト（PDF ヘッダー付き）
        large_content = b"%PDF-1.4\n" + b"x" * (10 * 1024 * 1024 + 1)
        large_file = io.BytesIO(large_content)
        large_file.name = "large.pdf"

        response = self.client.post(self.url, {"pdf_file": large_file})

        # フォームバリデーション失敗 → 200 で再表示
        self.assertEqual(response.status_code, 200)
        # サイズ制限エラーが含まれること
        self.assertIn("form", response.context)
        form_errors = response.context["form"].errors
        self.assertTrue(form_errors)
        # エラーメッセージにサイズ制限の説明が含まれること
        error_text = str(form_errors)
        self.assertIn("10MB", error_text)
