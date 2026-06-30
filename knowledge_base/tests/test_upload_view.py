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


class IngestHelperTest(TestCase):
    """_ingest 内部ヘルパーのユニットテスト

    抽出→分割→埋め込みを 1 ステップに集約した再利用可能ヘルパーの契約を検証する。
    - 成功時：(chunks, vectors) を返し、長さが一致すること
    - 埋め込み入力にファイル名がコンテキスト注入されること（保存用 chunk は元のまま）
    - 抽出テキストが空（画像型 PDF）の場合は ValueError を送出すること
    """

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_ingest_returns_chunks_and_vectors(self, mock_processor, mock_embedder):
        """成功時は元の chunk と、ファイル名注入済みテキストの埋め込みを返す"""
        from knowledge_base.views import _ingest

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["chunk-a", "chunk-b"]
        mock_embedder.embed_many.return_value = [[0.1] * 384, [0.2] * 384]

        chunks, vectors = _ingest(b"%PDF-bytes", "doc.pdf", "manual")

        # 保存用 chunk は元のテキストのまま（ファイル名注入なし）
        self.assertEqual(chunks, ["chunk-a", "chunk-b"])
        # chunk と vector は同じ長さ
        self.assertEqual(len(chunks), len(vectors))
        # 埋め込み入力にはファイル名がコンテキスト注入されること
        mock_embedder.embed_many.assert_called_once_with(
            ["doc.pdf\n\nchunk-a", "doc.pdf\n\nchunk-b"]
        )

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_ingest_raises_on_empty_text(self, mock_processor, mock_embedder):
        """抽出テキストが空白のみの場合は ValueError を送出する（画像型 PDF）"""
        from knowledge_base.views import _ingest

        mock_processor.extract_text.return_value = "   "

        with self.assertRaises(ValueError):
            _ingest(b"%PDF-bytes", "image_only.pdf", "")


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

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_post_valid_pdf_calls_extract_text(self, mock_processor, mock_embedder):
        """有効な PDF の POST は processor.extract_text を呼び出す"""
        # processor.extract_text が有効なテキストを返すようにモック
        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        pdf_bytes = _make_pdf_bytes("Sample text content")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "valid.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        mock_processor.extract_text.assert_called_once()

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_post_valid_pdf_calls_embed_many(self, mock_processor, mock_embedder):
        """有効な PDF の POST は embedder.embed_many を呼び出す"""
        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        pdf_bytes = _make_pdf_bytes("Sample text content")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "valid.pdf"

        self.client.post(self.url, {"pdf_file": pdf_file})

        # ファイル名コンテキスト注入済みテキストで呼び出されること
        mock_embedder.embed_many.assert_called_once_with(["valid.pdf\n\nSample text content"])

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_post_valid_pdf_redirects_to_document_detail(
        self, mock_processor, mock_embedder
    ):
        """有効な PDF の POST は /documents/{id}/ にリダイレクトする"""
        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        pdf_bytes = _make_pdf_bytes("Sample text content")
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "valid.pdf"

        response = self.client.post(self.url, {"pdf_file": pdf_file})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/documents/", response["Location"])

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
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


class UploadViewSameNameReplaceTest(TestCase):
    """同名アップロード時の置換挙動テスト（要件 1.1 / 1.2 / 1.3）

    - 同名アップロード → 新規行を増やさず既存ドキュメントを再利用（id 不変）
    - 別名アップロード → 既存の新規作成パスでちょうど 1 行追加
    - 同名かつ別カテゴリ → ファイル名のみで判定するため置換（新規行なし）
    """

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def _post_pdf(self, name, text="Sample text content", category=None):
        """PDF を 1 件 POST するヘルパー"""
        pdf_bytes = _make_pdf_bytes(text)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = name
        data = {"pdf_file": pdf_file}
        if category is not None:
            data["category"] = category
        return self.client.post(self.url, data)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_same_name_upload_reuses_document(self, mock_processor, mock_embedder):
        """同名アップロードは Document 行数を増やさず既存 id を再利用する（1.1, 2.1）"""
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        # 1 回目アップロード（新規作成）
        self._post_pdf("same.pdf")
        self.assertEqual(Document.objects.count(), 1)
        original_id = Document.objects.get().id

        # 2 回目アップロード（同名 → 置換）
        self._post_pdf("same.pdf")

        # 行数は増えず、同じ id を再利用していること
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(Document.objects.get().id, original_id)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_different_name_upload_adds_new_document(
        self, mock_processor, mock_embedder
    ):
        """別名アップロードはちょうど 1 行追加する（1.2）"""
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        self._post_pdf("first.pdf")
        self.assertEqual(Document.objects.count(), 1)

        self._post_pdf("second.pdf")
        self.assertEqual(Document.objects.count(), 2)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_same_name_different_category_still_replaces(
        self, mock_processor, mock_embedder
    ):
        """同名かつ別カテゴリでも置換（ファイル名のみで判定）（1.3）"""
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        # 1 回目：category=manual
        self._post_pdf("same.pdf", category=Document.CATEGORY_MANUAL)
        self.assertEqual(Document.objects.count(), 1)
        original_id = Document.objects.get().id

        # 2 回目：同名・category=policy → 置換（新規行なし）
        self._post_pdf("same.pdf", category=Document.CATEGORY_POLICY)

        self.assertEqual(Document.objects.count(), 1)
        target = Document.objects.get()
        self.assertEqual(target.id, original_id)
        # 種別が新しい内容で更新されていること（2.3 の一部）
        self.assertEqual(target.category, Document.CATEGORY_POLICY)


class ReplaceDocumentPersistenceTest(TestCase):
    """置換持久化の堅牢化テスト（タスク 2.3 / 要件 1.4・2.1・2.2・2.3）

    2.2 の最小実装に対し、本タスクで追加する新挙動を検証する:
    - 重複クリーンアップ: 同名重複が複数存在しても置換後はちょうど 1 件に収束（1.4）
    - 旧物理ファイルの commit 後削除: on_commit で旧ファイルがストレージから消える
    - 分块再構築の正しさ: 旧チャンク全削除・新内容で再生成・chunk_count 更新（2.2, 2.3）
    - id 不変・フィールド更新（2.1, 2.3）
    """

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def _post_pdf(self, name, text="Sample text content", category=None):
        """PDF を 1 件 POST するヘルパー"""
        pdf_bytes = _make_pdf_bytes(text)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = name
        data = {"pdf_file": pdf_file}
        if category is not None:
            data["category"] = category
        return self.client.post(self.url, data)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_removes_duplicate_same_name_documents(
        self, mock_processor, mock_embedder
    ):
        """同名重複が複数あっても置換後はその filename がちょうど 1 件に収束する（1.4）"""
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        # 歴史的な重複行を手動で 3 件作成（同名・status は問わない）
        d1 = Document.objects.create(filename="dup.pdf", status=Document.STATUS_COMPLETE)
        d2 = Document.objects.create(filename="dup.pdf", status=Document.STATUS_COMPLETE)
        d3 = Document.objects.create(filename="dup.pdf", status=Document.STATUS_COMPLETE)
        self.assertEqual(Document.objects.filter(filename="dup.pdf").count(), 3)

        # 同名アップロード → 置換
        self._post_pdf("dup.pdf")

        # 置換後、この filename に対応する Document はちょうど 1 件
        remaining = Document.objects.filter(filename="dup.pdf")
        self.assertEqual(remaining.count(), 1)
        # 残った行は -uploaded_at の最新（最後に作成した d3）= 置換対象
        self.assertEqual(remaining.get().id, d3.id)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_deletes_old_physical_file_after_commit(
        self, mock_processor, mock_embedder
    ):
        """置換成功後、旧物理ファイルがストレージから削除される（commit 後）"""
        from django.core.files.storage import default_storage
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        # 1 回目アップロード（新規作成 → 原本ファイル保存）
        self._post_pdf("file.pdf")
        doc = Document.objects.get(filename="file.pdf")
        old_name = doc.file.name
        self.assertTrue(default_storage.exists(old_name))

        # 2 回目アップロード（同名 → 置換）。on_commit を実際に実行させる
        with self.captureOnCommitCallbacks(execute=True):
            self._post_pdf("file.pdf")

        doc.refresh_from_db()
        new_name = doc.file.name
        # ファイル参照が切り替わっていること
        self.assertNotEqual(new_name, old_name)
        # 旧物理ファイルは削除済み、新ファイルは存在
        self.assertFalse(default_storage.exists(old_name))
        self.assertTrue(default_storage.exists(new_name))

        # テスト後始末（新ファイルを削除）
        if default_storage.exists(new_name):
            default_storage.delete(new_name)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_rebuilds_chunks_and_updates_fields(
        self, mock_processor, mock_embedder
    ):
        """旧チャンク全削除 → 新内容で再生成、chunk_count/category/status を更新（2.2, 2.3）"""
        from knowledge_base.models import Chunk, Document

        # 1 回目：2 チャンク
        mock_processor.extract_text.return_value = "old content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["old-a", "old-b"]
        mock_embedder.embed_many.return_value = [[0.1] * 384, [0.2] * 384]

        self._post_pdf("rebuild.pdf", category=Document.CATEGORY_MANUAL)
        doc = Document.objects.get(filename="rebuild.pdf")
        original_id = doc.id
        old_chunk_ids = set(doc.chunks.values_list("id", flat=True))
        self.assertEqual(len(old_chunk_ids), 2)

        # 2 回目：同名・3 チャンク・別カテゴリ
        mock_processor.extract_text.return_value = "new content"
        mock_processor.split_into_chunks.return_value = ["new-a", "new-b", "new-c"]
        mock_embedder.embed_many.return_value = [[0.3] * 384, [0.4] * 384, [0.5] * 384]

        self._post_pdf("rebuild.pdf", category=Document.CATEGORY_POLICY)

        doc.refresh_from_db()
        # id 不変（2.1）
        self.assertEqual(doc.id, original_id)
        # 旧チャンクは全削除され新チャンクへ置き換わっている（2.2）
        new_chunk_ids = set(doc.chunks.values_list("id", flat=True))
        self.assertEqual(doc.chunks.count(), 3)
        self.assertTrue(old_chunk_ids.isdisjoint(new_chunk_ids))
        # 旧チャンク id は DB から消えている
        self.assertFalse(Chunk.objects.filter(id__in=old_chunk_ids).exists())
        # 新内容で再生成されていること
        self.assertEqual(
            list(doc.chunks.order_by("position").values_list("content", flat=True)),
            ["new-a", "new-b", "new-c"],
        )
        # フィールド更新（2.3）
        self.assertEqual(doc.chunk_count, 3)
        self.assertEqual(doc.category, Document.CATEGORY_POLICY)
        self.assertEqual(doc.status, Document.STATUS_COMPLETE)
        self.assertEqual(doc.error_message, "")

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_old_content_chunks_not_retrievable(
        self, mock_processor, mock_embedder
    ):
        """置換成功後、旧内容の分块は永続層から取得できない（要件 2.5）

        ベクトル検索（CosineDistance）は Postgres 専用であり、テスト DB は sqlite のため
        実検索は実行できない。そこで「検索が消費する永続層」で検証する:
        置換後にドキュメントの分块を問い合わせると、新内容の文字列のみが含まれ、
        旧内容の文字列は一切含まれず、旧 chunk 行（id 単位）も DB から消えていること。
        これは検索整合性（旧分块を返さない）の永続層での保証に相当する。
        旧 chunk が残存していれば本テストは失敗する。
        """
        from knowledge_base.models import Chunk, Document

        # 1 回目：旧内容で 2 チャンク
        mock_processor.extract_text.return_value = "old content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = [
            "古い秘密の内容A",
            "古い秘密の内容B",
        ]
        mock_embedder.embed_many.return_value = [[0.1] * 384, [0.2] * 384]

        self._post_pdf("retr.pdf")
        doc = Document.objects.get(filename="retr.pdf")
        old_chunk_ids = set(doc.chunks.values_list("id", flat=True))
        old_contents = {"古い秘密の内容A", "古い秘密の内容B"}
        self.assertEqual(len(old_chunk_ids), 2)

        # 2 回目：同名・新内容（旧内容と完全に異なる）で置換
        mock_processor.extract_text.return_value = "new content"
        mock_processor.split_into_chunks.return_value = [
            "新しい内容X",
            "新しい内容Y",
            "新しい内容Z",
        ]
        mock_embedder.embed_many.return_value = [[0.3] * 384, [0.4] * 384, [0.5] * 384]

        self._post_pdf("retr.pdf")

        doc.refresh_from_db()
        # 永続層（検索が消費する分块集合）に現存する内容を取得
        current_contents = set(
            doc.chunks.values_list("content", flat=True)
        )

        # 新内容のみが取得可能であること
        self.assertEqual(current_contents, {"新しい内容X", "新しい内容Y", "新しい内容Z"})
        # 旧内容の文字列は一切含まれないこと（検索で旧分块を返さない保証）
        for old in old_contents:
            self.assertNotIn(old, current_contents)
        # ドキュメント全体で見ても旧内容の分块は存在しない
        self.assertFalse(
            Chunk.objects.filter(document=doc, content__in=old_contents).exists()
        )
        # 旧 chunk 行（id 単位）は DB から完全に消えている
        self.assertFalse(Chunk.objects.filter(id__in=old_chunk_ids).exists())

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_detail_page_reflects_latest_after_replace(
        self, mock_processor, mock_embedder
    ):
        """置換成功後、詳情ページが最新の種別と分块数を反映する（要件 2.4）

        置換でカテゴリと分块数が変わった後に詳細ページを GET し、
        - context の document が新カテゴリを保持していること
        - 描画される chunk_count（テンプレートが表示）が新しい値であること
        を検証する。詳細テンプレートは status=complete のとき chunk_count を表示するため、
        新しい分块数がページ本文に現れることまで確認する。
        """
        from knowledge_base.models import Document

        # 1 回目：manual・2 チャンク
        mock_processor.extract_text.return_value = "old content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["old-a", "old-b"]
        mock_embedder.embed_many.return_value = [[0.1] * 384, [0.2] * 384]

        self._post_pdf("detail.pdf", category=Document.CATEGORY_MANUAL)
        doc = Document.objects.get(filename="detail.pdf")

        # 2 回目：同名・policy・3 チャンクで置換
        mock_processor.extract_text.return_value = "new content"
        mock_processor.split_into_chunks.return_value = ["new-a", "new-b", "new-c"]
        mock_embedder.embed_many.return_value = [[0.3] * 384, [0.4] * 384, [0.5] * 384]

        self._post_pdf("detail.pdf", category=Document.CATEGORY_POLICY)

        # 詳細ページを GET
        detail_url = reverse("knowledge_base:document_detail", args=[doc.pk])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

        # context の document が新カテゴリ・新分块数を反映していること（2.4）
        ctx_doc = response.context["document"]
        self.assertEqual(ctx_doc.category, Document.CATEGORY_POLICY)
        self.assertEqual(ctx_doc.chunk_count, 3)

        # 描画本文に新しい分块数が現れること（テンプレートが表示する最新内容）
        content = response.content.decode("utf-8")
        self.assertIn("3 チャンク", content)

        # 描画本文に新しい種別の表示名が現れ、旧種別は現れないこと（要件 2.4）
        self.assertIn(
            dict(Document.CATEGORY_CHOICES)[Document.CATEGORY_POLICY], content
        )
        self.assertNotIn(
            dict(Document.CATEGORY_CHOICES)[Document.CATEGORY_MANUAL], content
        )

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_moves_file_to_new_category_folder(
        self, mock_processor, mock_embedder
    ):
        """種別を変えて置換すると、新原本ファイルが新種別フォルダ配下へ保存される（回帰）

        保存先パス _pdf_upload_path は instance.category を参照する。
        file.save() の前に新種別を設定していないと旧種別フォルダへ保存される不具合の回帰テスト。
        """
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["a"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        # 1 回目：manual フォルダに保存される
        self._post_pdf("cat.pdf", category=Document.CATEGORY_MANUAL)
        doc = Document.objects.get(filename="cat.pdf")
        self.assertIn("pdfs/manual/", doc.file.name)
        self.addCleanup(lambda: doc.file.storage.delete(doc.file.name))

        # 2 回目：同名・policy で置換 → 新ファイルは policy フォルダへ
        self._post_pdf("cat.pdf", category=Document.CATEGORY_POLICY)
        doc.refresh_from_db()
        self.assertIn("pdfs/policy/", doc.file.name)
        self.assertNotIn("pdfs/manual/", doc.file.name)

    @patch("knowledge_base.views.timezone")
    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_updates_uploaded_at(
        self, mock_processor, mock_embedder, mock_timezone
    ):
        """置換時に uploaded_at が最新の置換時刻へ更新される（選択肢B）

        uploaded_at は auto_now_add のため通常の UPDATE では変わらない。
        置換＝再アップロードとみなし、_replace_document が timezone.now() で明示更新する。
        timezone.now() を決定的に固定して検証する。
        """
        from datetime import timedelta

        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["a"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        # 1 回目：作成（uploaded_at は auto_now_add で作成時刻）
        # 作成パスは views.timezone を使わない（auto_now_add は内部で別参照）ため original は実時刻
        self._post_pdf("ts.pdf")
        doc = Document.objects.get(filename="ts.pdf")
        original = doc.uploaded_at

        # 置換時刻を元時刻より後に固定する
        replaced_at = original + timedelta(hours=1)
        mock_timezone.now.return_value = replaced_at

        # 2 回目：同名で置換 → uploaded_at が固定した置換時刻へ更新される
        self._post_pdf("ts.pdf")
        doc.refresh_from_db()
        self.assertEqual(doc.uploaded_at, replaced_at)
        self.assertGreater(doc.uploaded_at, original)


class UploadSuccessFeedbackTest(TestCase):
    """アップロード成功時のフィードバックと跳转テスト（タスク 2.5 / 要件 4.1・4.2・4.3）

    - 置換成功 → success レベルの flash「置き換え」を提示し、既存ドキュメント詳細へ跳转（4.1, 4.3）
    - 新規作成成功 → success レベルの flash「作成」を提示し、新ドキュメント詳細へ跳转（4.2, 4.3）
    - 新規作成が失敗（画像型 PDF 等）した場合は「作成」success メッセージを出さない
    """

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def _post_pdf(self, name, text="Sample text content", category=None, follow=False):
        """PDF を 1 件 POST するヘルパー"""
        pdf_bytes = _make_pdf_bytes(text)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = name
        data = {"pdf_file": pdf_file}
        if category is not None:
            data["category"] = category
        return self.client.post(self.url, data, follow=follow)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_success_shows_replace_flash_and_redirects(
        self, mock_processor, mock_embedder
    ):
        """置換成功時は success レベルの「置き換え」flash を提示し既存詳細へ跳转する（4.1, 4.3）"""
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        # 1 回目アップロード（新規作成）
        self._post_pdf("same.pdf")
        existing = Document.objects.get(filename="same.pdf")

        # 2 回目アップロード（同名 → 置換）。follow=True で跳转先の messages を取得
        response = self._post_pdf("same.pdf", follow=True)

        # 既存ドキュメントの詳細ページへ跳转していること（4.3）
        self.assertEqual(response.redirect_chain[-1][0], f"/documents/{existing.id}/")

        msgs = list(response.context["messages"])
        success_msgs = [m for m in msgs if m.level_tag == "success"]
        self.assertTrue(len(success_msgs) >= 1)
        # 置換を示す文言を含む success メッセージが存在すること（日本語、4.1）
        self.assertTrue(
            any("置き換え" in str(m) for m in success_msgs),
            f"「置き換え」success メッセージが見つかりません: {[str(m) for m in success_msgs]}",
        )

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_new_upload_success_shows_create_flash_and_redirects(
        self, mock_processor, mock_embedder
    ):
        """新規作成成功時は success レベルの「作成」flash を提示し新詳細へ跳转する（4.2, 4.3）"""
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "Sample text content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["Sample text content"]
        mock_embedder.embed_many.return_value = [[0.1] * 384]

        response = self._post_pdf("new.pdf", follow=True)

        doc = Document.objects.get(filename="new.pdf")
        # 新ドキュメントの詳細ページへ跳转していること（4.3）
        self.assertEqual(response.redirect_chain[-1][0], f"/documents/{doc.id}/")

        msgs = list(response.context["messages"])
        success_msgs = [m for m in msgs if m.level_tag == "success"]
        self.assertTrue(len(success_msgs) >= 1)
        # 新規作成を示す文言を含む success メッセージが存在すること（日本語、4.2）
        self.assertTrue(
            any("作成" in str(m) for m in success_msgs),
            f"「作成」success メッセージが見つかりません: {[str(m) for m in success_msgs]}",
        )

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_new_upload_failure_shows_no_create_success_flash(
        self, mock_processor, mock_embedder
    ):
        """新規作成の ingestion が失敗した場合は「作成」success メッセージを出さない"""
        # 抽出テキストが空 → _ingest が ValueError → status=failed
        mock_processor.extract_text.return_value = "   "
        mock_embedder.embed_many.return_value = []

        response = self._post_pdf("image_only.pdf", follow=True)

        msgs = list(response.context["messages"])
        success_msgs = [m for m in msgs if m.level_tag == "success"]
        # 失敗時は success メッセージが存在しないこと
        self.assertEqual(len(success_msgs), 0)


class ReplaceFailureDataSafetyTest(TestCase):
    """置換失敗時のデータ安全テスト（タスク 2.4 / 要件 3.1・3.2・3.3）

    置換パスで ingestion（抽出 / 分割 / 埋め込み）が失敗した場合の挙動を検証する:
    - 既存ドキュメントとそのチャンクは置換前の状態を完全に維持する（status / chunk_count / chunks 不変）
    - 既存ドキュメントの error_message は書き換えられない（新規パスと異なり flash で通知）
    - flash エラーメッセージ（messages.error）が提示される
    - 既存ドキュメント（旧・有効内容を保持）の詳細ページへリダイレクトする
    """

    def setUp(self):
        self.client = Client()
        self.url = reverse("knowledge_base:upload")

    def _post_pdf(self, name, text="Sample text content", category=None, follow=False):
        """PDF を 1 件 POST するヘルパー"""
        pdf_bytes = _make_pdf_bytes(text)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = name
        data = {"pdf_file": pdf_file}
        if category is not None:
            data["category"] = category
        return self.client.post(self.url, data, follow=follow)

    def _seed_existing(self, mock_processor, mock_embedder, name="exist.pdf"):
        """既存の有効ドキュメントを 1 件作成して返す（2 チャンク・complete）"""
        from knowledge_base.models import Document

        mock_processor.extract_text.return_value = "old content"
        mock_processor.chunk_config_for_category.return_value = (700, 150)
        mock_processor.split_into_chunks.return_value = ["old-a", "old-b"]
        mock_embedder.embed_many.return_value = [[0.1] * 384, [0.2] * 384]

        self._post_pdf(name, category=Document.CATEGORY_MANUAL)
        return Document.objects.get(filename=name)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_empty_text_preserves_existing_document(
        self, mock_processor, mock_embedder
    ):
        """置換時に抽出テキストが空（画像型 PDF）でも既存ドキュメント・チャンクは不変（3.1, 3.2）"""
        from knowledge_base.models import Chunk, Document

        existing = self._seed_existing(mock_processor, mock_embedder, "exist.pdf")
        original_id = existing.id
        original_status = existing.status
        original_chunk_count = existing.chunk_count
        original_chunk_ids = set(existing.chunks.values_list("id", flat=True))
        self.assertEqual(len(original_chunk_ids), 2)

        # 2 回目：同名アップロードだが抽出テキストが空 → _ingest が ValueError
        mock_processor.extract_text.return_value = "   "

        self._post_pdf("exist.pdf")

        # 行数は増えていない（置換パスのまま）
        self.assertEqual(Document.objects.filter(filename="exist.pdf").count(), 1)

        existing.refresh_from_db()
        # id・status・chunk_count・error_message すべて不変（3.1, 3.3）
        self.assertEqual(existing.id, original_id)
        self.assertEqual(existing.status, original_status)
        self.assertEqual(existing.chunk_count, original_chunk_count)
        self.assertEqual(existing.error_message, "")
        # チャンクは削除も再生成もされていない（3.1, 3.2）
        new_chunk_ids = set(existing.chunks.values_list("id", flat=True))
        self.assertEqual(new_chunk_ids, original_chunk_ids)
        self.assertEqual(existing.chunks.count(), 2)
        self.assertEqual(
            list(existing.chunks.order_by("position").values_list("content", flat=True)),
            ["old-a", "old-b"],
        )
        # 旧チャンクは DB に残っている
        self.assertTrue(Chunk.objects.filter(id__in=original_chunk_ids).count() == 2)

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_failure_redirects_to_existing_detail(
        self, mock_processor, mock_embedder
    ):
        """置換失敗時は既存ドキュメントの詳細ページへリダイレクトする（3.3）"""
        existing = self._seed_existing(mock_processor, mock_embedder, "exist.pdf")

        mock_processor.extract_text.return_value = "   "
        response = self._post_pdf("exist.pdf")

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/documents/{existing.id}/", response["Location"])

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_failure_adds_flash_error_message(
        self, mock_processor, mock_embedder
    ):
        """置換失敗時は error レベルの flash メッセージが提示される（3.3）"""
        self._seed_existing(mock_processor, mock_embedder, "exist.pdf")

        mock_processor.extract_text.return_value = "   "
        # follow=True でリダイレクト先まで辿り、messages を context から取得
        response = self._post_pdf("exist.pdf", follow=True)

        msgs = list(response.context["messages"])
        # 少なくとも 1 件の error レベルメッセージが存在する
        self.assertTrue(len(msgs) >= 1)
        error_msgs = [m for m in msgs if m.level_tag == "error"]
        self.assertTrue(len(error_msgs) >= 1)
        # 失敗を示す文言が含まれること（日本語）
        self.assertIn("失敗", str(error_msgs[0]))

    @patch("knowledge_base.views.embedder")
    @patch("knowledge_base.views.processor")
    def test_replace_embedding_failure_preserves_existing_document(
        self, mock_processor, mock_embedder
    ):
        """置換時に埋め込み生成が例外を送出しても既存データは完全に保全される（3.1）"""
        from knowledge_base.models import Document

        existing = self._seed_existing(mock_processor, mock_embedder, "exist.pdf")
        original_chunk_ids = set(existing.chunks.values_list("id", flat=True))

        # 2 回目：抽出は成功するが embed_many が例外を送出
        mock_processor.extract_text.return_value = "new valid content"
        mock_processor.split_into_chunks.return_value = ["new-a", "new-b"]
        mock_embedder.embed_many.side_effect = RuntimeError("embedding service down")

        response = self._post_pdf("exist.pdf")

        # 既存データは不変
        existing.refresh_from_db()
        self.assertEqual(existing.status, Document.STATUS_COMPLETE)
        self.assertEqual(existing.error_message, "")
        self.assertEqual(
            set(existing.chunks.values_list("id", flat=True)), original_chunk_ids
        )
        # 既存詳細へリダイレクト
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/documents/{existing.id}/", response["Location"])
