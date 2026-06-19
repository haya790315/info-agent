"""
DocumentDetailView のテスト
テスト対象：kb/views.py (DocumentDetailView)、kb/urls.py
"""
from django.test import Client, TestCase
from django.urls import reverse

from knowledge_base.models import Document


class DocumentDetailViewNotFoundTest(TestCase):
    """存在しない pk へのアクセスのテスト"""

    def setUp(self):
        self.client = Client()

    def test_get_nonexistent_pk_returns_404(self):
        """存在しない pk への GET は HTTP 404 を返す"""
        url = reverse("knowledge_base:document_detail", kwargs={"pk": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class DocumentDetailViewCompleteTest(TestCase):
    """status=complete のドキュメント詳細ページのテスト"""

    def setUp(self):
        self.client = Client()
        self.doc = Document.objects.create(
            filename="sample.pdf",
            status=Document.STATUS_COMPLETE,
            chunk_count=42,
        )
        self.url = reverse("knowledge_base:document_detail", kwargs={"pk": self.doc.pk})

    def test_get_complete_doc_returns_200(self):
        """status=complete のドキュメントへの GET は HTTP 200 を返す"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_complete_doc_contains_filename(self):
        """レスポンスにファイル名が含まれる"""
        response = self.client.get(self.url)
        self.assertContains(response, "sample.pdf")

    def test_get_complete_doc_contains_status_label(self):
        """レスポンスに「処理完了」が含まれる"""
        response = self.client.get(self.url)
        self.assertContains(response, "処理完了")

    def test_get_complete_doc_contains_chunk_count(self):
        """レスポンスに chunk_count が含まれる"""
        response = self.client.get(self.url)
        self.assertContains(response, "42")

    def test_get_complete_doc_uses_base_template(self):
        """kb/base.html テンプレートが使用される"""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "kb/base.html")

    def test_get_complete_doc_uses_detail_template(self):
        """kb/document_detail.html テンプレートが使用される"""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "kb/document_detail.html")


class DocumentDetailViewFailedTest(TestCase):
    """status=failed のドキュメント詳細ページのテスト"""

    def setUp(self):
        self.client = Client()
        self.doc = Document.objects.create(
            filename="broken.pdf",
            status=Document.STATUS_FAILED,
            error_message="テキスト抽出に失敗しました",
        )
        self.url = reverse("knowledge_base:document_detail", kwargs={"pk": self.doc.pk})

    def test_get_failed_doc_returns_200(self):
        """status=failed のドキュメントへの GET は HTTP 200 を返す"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_failed_doc_contains_status_label(self):
        """レスポンスに「処理失敗」が含まれる"""
        response = self.client.get(self.url)
        self.assertContains(response, "処理失敗")

    def test_get_failed_doc_contains_error_message(self):
        """レスポンスに error_message が含まれる"""
        response = self.client.get(self.url)
        self.assertContains(response, "テキスト抽出に失敗しました")


class DocumentDetailViewPendingTest(TestCase):
    """status=pending のドキュメント詳細ページのテスト"""

    def setUp(self):
        self.client = Client()
        self.doc = Document.objects.create(
            filename="waiting.pdf",
            status=Document.STATUS_PENDING,
        )
        self.url = reverse("knowledge_base:document_detail", kwargs={"pk": self.doc.pk})

    def test_get_pending_doc_returns_200(self):
        """status=pending のドキュメントへの GET は HTTP 200 を返す"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_pending_doc_contains_status_label(self):
        """レスポンスに「処理待ち」が含まれる"""
        response = self.client.get(self.url)
        self.assertContains(response, "処理待ち")


class DocumentDetailViewProcessingTest(TestCase):
    """status=processing のドキュメント詳細ページのテスト"""

    def setUp(self):
        self.client = Client()
        self.doc = Document.objects.create(
            filename="running.pdf",
            status=Document.STATUS_PROCESSING,
        )
        self.url = reverse("knowledge_base:document_detail", kwargs={"pk": self.doc.pk})

    def test_get_processing_doc_returns_200(self):
        """status=processing のドキュメントへの GET は HTTP 200 を返す"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_processing_doc_contains_status_label(self):
        """レスポンスに「処理中」が含まれる"""
        response = self.client.get(self.url)
        self.assertContains(response, "処理中")
