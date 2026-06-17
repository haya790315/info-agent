"""
原本ファイル保存 + 詳細ページ閲覧リンクのテスト（Task 5.2 / 5.3）
SQLite テスト環境では VectorField/CosineDistance が使えないため、
Chunk 一括保存と埋め込み生成はモックで代替する。
原本ファイルはテスト専用の一時 MEDIA_ROOT に保存し、後片付けする。
"""
import io
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from knowledge_base.models import Document

# テスト中のアップロード原本を隔離する一時ディレクトリ
_TMP_MEDIA = tempfile.mkdtemp(prefix="kb_test_media_")


def _make_pdf_bytes(text: str = "Hello World") -> bytes:
    """テスト用の最小 PDF バイト列を生成するヘルパー"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class OriginalFilePersistenceTest(TestCase):
    """アップロードした原本 PDF が保存されることを検証する（要件 11.1）"""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    @patch("knowledge_base.views.Chunk.objects.bulk_create")
    @patch("knowledge_base.views.embedder.embed_many")
    def test_uploaded_pdf_is_persisted_with_matching_bytes(
        self, mock_embed_many, mock_bulk_create
    ):
        """テキスト入り PDF アップロード後、Document.file が非空かつバイトが一致する"""
        mock_embed_many.return_value = [[0.1] * 384]
        mock_bulk_create.return_value = MagicMock()

        pdf_bytes = _make_pdf_bytes("storage persistence test")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "store_me.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        doc = Document.objects.last()
        self.assertIsNotNone(doc)
        self.assertTrue(doc.file)  # ファイルが保存されている
        with doc.file.open("rb") as fh:
            self.assertEqual(fh.read(), pdf_bytes)  # 保存内容がアップロード内容と一致

    @patch("knowledge_base.views.processor.extract_text")
    def test_failed_ingestion_still_keeps_original_file(self, mock_extract_text):
        """ingestion 失敗（画像型 PDF）でも原本 PDF は保持される（要件 11.1）"""
        # extract_text が空文字 → ingestion は failed になる
        mock_extract_text.return_value = ""

        pdf_bytes = _make_pdf_bytes("image only")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "image_only_keep.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        doc = Document.objects.last()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.status, Document.STATUS_FAILED)
        self.assertTrue(doc.file)  # 失敗しても原本は残る


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class DetailViewOriginalLinkTest(TestCase):
    """詳細ページの「原文を表示」リンク表示/非表示を検証する（要件 5.5）"""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()

    def test_detail_shows_link_when_file_present(self):
        """原本ファイルがある場合、詳細ページに原文リンクが表示される"""
        doc = Document.objects.create(
            filename="with_file.pdf",
            status=Document.STATUS_COMPLETE,
            chunk_count=1,
        )
        doc.file.save("with_file.pdf", ContentFile(b"%PDF-1.4 dummy"), save=True)

        resp = self.client.get(
            reverse("knowledge_base:document_detail", args=[doc.pk])
        )
        self.assertContains(resp, "原文を表示")
        self.assertContains(resp, doc.file.url)

    def test_detail_hides_link_when_no_file(self):
        """原本ファイルがない場合、原文リンクは表示されない"""
        doc = Document.objects.create(
            filename="no_file.pdf",
            status=Document.STATUS_PENDING,
        )

        resp = self.client.get(
            reverse("knowledge_base:document_detail", args=[doc.pk])
        )
        self.assertNotContains(resp, "原文を表示")
