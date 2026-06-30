"""
読み取り専用 JSON API のテスト（Task 6.1 / 6.2）
SQLite テスト環境では pgvector の CosineDistance（<=> 演算子）が使えないため、
検索エンドポイントのテストは embedder/searcher をモックしてビュー層の契約を検証する。
原本ファイルはテスト専用の一時 MEDIA_ROOT に保存する。
"""
import json
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

import knowledge_base.api_views as api_views
from knowledge_base.models import Chunk, Document

_TMP_MEDIA = tempfile.mkdtemp(prefix="kb_test_api_media_")


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class DocumentListAPITest(TestCase):
    """GET /api/documents/ （要件 9.1, 9.2, 9.3, 11.4）"""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:api_document_list")

    def test_empty_db_returns_empty_array(self):
        """ドキュメントがない場合は空配列を返す（エラーではない）"""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"documents": []})

    def test_list_includes_file_url_each(self):
        """各ドキュメント項目に file_url が含まれる（保存済みは絶対 URL、未保存は null）"""
        d1 = Document.objects.create(
            filename="a.pdf", status=Document.STATUS_COMPLETE, chunk_count=2
        )
        d1.file.save("a.pdf", ContentFile(b"%PDF"), save=True)
        Document.objects.create(filename="b.pdf", status=Document.STATUS_PENDING)

        docs = self.client.get(self.url).json()["documents"]
        self.assertEqual(len(docs), 2)
        for d in docs:
            self.assertIn("file_url", d)
        by_name = {d["filename"]: d for d in docs}
        self.assertTrue(by_name["a.pdf"]["file_url"].startswith("http"))
        self.assertIsNone(by_name["b.pdf"]["file_url"])

    def test_response_is_pure_json(self):
        """レスポンスは純 JSON（HTML ラップなし）"""
        resp = self.client.get(self.url)
        self.assertNotIn(b"<html", resp.content.lower())


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class DocumentDetailAPITest(TestCase):
    """GET /api/documents/<pk>/ （要件 10.1, 10.2, 10.3, 11.4）"""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()

    def test_valid_pk_returns_full_fields(self):
        """有効な pk で全フィールド + file_url を返す"""
        doc = Document.objects.create(
            filename="detail.pdf", status=Document.STATUS_COMPLETE, chunk_count=3
        )
        doc.file.save("detail.pdf", ContentFile(b"%PDF"), save=True)

        resp = self.client.get(
            reverse("knowledge_base:api_document_detail", args=[doc.pk])
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in (
            "id", "filename", "status", "chunk_count",
            "uploaded_at", "error_message", "file_url",
        ):
            self.assertIn(key, body)
        self.assertEqual(body["filename"], "detail.pdf")
        self.assertTrue(body["file_url"].startswith("http"))

    def test_missing_pk_returns_404_json(self):
        """存在しない pk は 404 + JSON エラー"""
        resp = self.client.get(
            reverse("knowledge_base:api_document_detail", args=[999999])
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.json())

    def test_file_url_is_null_when_no_file(self):
        """原本ファイル未保存のドキュメントは file_url が null"""
        doc = Document.objects.create(
            filename="nofile.pdf", status=Document.STATUS_PENDING
        )
        resp = self.client.get(
            reverse("knowledge_base:api_document_detail", args=[doc.pk])
        )
        self.assertIsNone(resp.json()["file_url"])


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class SearchAPITest(TestCase):
    """POST /api/search/ （要件 8.1, 8.2, 8.3, 8.4, 8.5, 11.4）

    実ベクトル検索は postgres 専用のため、embedder/searcher をモックして
    ビュー層の契約（JSON 形・400・空結果・file_url・csrf 免除）を検証する。
    """

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:api_search")

    def _post(self, payload, client=None):
        return (client or self.client).post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

    def test_empty_query_returns_400_without_calling_services(self):
        """空クエリは 400 を返し、embedder/searcher を呼ばない（要件 8.4）"""
        with patch.object(api_views.embedder, "embed_one") as m_embed, \
             patch.object(api_views.searcher, "search") as m_search:
            resp = self._post({"query": ""})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())
        m_embed.assert_not_called()
        m_search.assert_not_called()

    def test_missing_query_key_returns_400(self):
        """query キー欠落も 400（空クエリ扱い）"""
        with patch.object(api_views.embedder, "embed_one") as m_embed, \
             patch.object(api_views.searcher, "search") as m_search:
            resp = self._post({})
        self.assertEqual(resp.status_code, 400)
        m_embed.assert_not_called()
        m_search.assert_not_called()

    def test_empty_results_when_no_chunks(self):
        """検索結果が空の場合は results=[]（200、エラーではない）（要件 8.5）"""
        with patch.object(api_views.embedder, "embed_one", return_value=[0.0] * 384), \
             patch.object(api_views.searcher, "search", return_value=[]):
            resp = self._post({"query": "anything"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"results": []})

    def test_results_include_content_filename_fileurl(self):
        """検索結果の各項目に content/filename/document_id/file_url が含まれる（要件 8.1, 11.4）"""
        doc = Document.objects.create(
            filename="src.pdf", status=Document.STATUS_COMPLETE, chunk_count=1
        )
        doc.file.save("src.pdf", ContentFile(b"%PDF"), save=True)
        # 未保存の Chunk インスタンス（searcher のモック戻り値として使用）
        # searcher は distance を annotate するため、その挙動を手動で再現する
        chunk = Chunk(
            document=doc, content="annual leave is 10 days",
            embedding=[0.0] * 384, position=0,
        )
        chunk.distance = 0.1234
        with patch.object(api_views.embedder, "embed_one", return_value=[0.0] * 384), \
             patch.object(api_views.searcher, "search", return_value=[chunk]):
            resp = self._post({"query": "leave"})
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item["content"], "annual leave is 10 days")
        self.assertEqual(item["filename"], "src.pdf")
        self.assertEqual(item["document_id"], doc.pk)
        self.assertTrue(item["file_url"].startswith("http"))
        # annotate された distance がそのまま（丸めて）返ること
        self.assertEqual(item["distance"], 0.1234)

    def test_response_is_pure_json(self):
        """レスポンスは純 JSON（HTML ラップなし）"""
        with patch.object(api_views.embedder, "embed_one", return_value=[0.0] * 384), \
             patch.object(api_views.searcher, "search", return_value=[]):
            resp = self._post({"query": "x"})
        self.assertNotIn(b"<html", resp.content.lower())

    def test_csrf_exempt_allows_post_without_token(self):
        """csrf 強制クライアントでも POST が通る（csrf_exempt の検証）"""
        csrf_client = Client(enforce_csrf_checks=True)
        with patch.object(api_views.embedder, "embed_one", return_value=[0.0] * 384), \
             patch.object(api_views.searcher, "search", return_value=[]):
            resp = self._post({"query": "x"}, client=csrf_client)
        self.assertEqual(resp.status_code, 200)
