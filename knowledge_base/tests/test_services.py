"""
サービス層の統合ユニットテスト
Task 4.1: ProcessorService, EmbedderService, SearcherService の検証
"""
import fitz  # PyMuPDF
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from knowledge_base.services.processor import extract_text, split_into_chunks
from knowledge_base.services.embedder import embed_one, embed_many
from knowledge_base.services.searcher import search


def _make_pdf_bytes(text: str = "Hello World") -> bytes:
    """テスト用の最小 PDF バイト列を生成するヘルパー"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ------------------------------------------------------------------ #
#  ProcessorService — split_into_chunks                               #
# ------------------------------------------------------------------ #

class SplitIntoChunksServiceTest(SimpleTestCase):
    """split_into_chunks のサービス層ユニットテスト"""

    def test_empty_string_returns_empty_list(self):
        # 空文字列は [] を返す
        result = split_into_chunks("")
        self.assertEqual(result, [])

    def test_1500_chars_returns_two_chunks(self):
        # 1500 文字は chunk_size=1000 のデフォルトで 2 チャンクに分割される
        text = "a" * 1500
        result = split_into_chunks(text)
        self.assertEqual(len(result), 2)

    def test_chunks_joined_equal_original_text(self):
        # 全チャンクを結合すると元のテキストと完全に一致する（文字の損失なし）
        text = "x" * 2500
        chunks = split_into_chunks(text)
        self.assertEqual("".join(chunks), text)


# ------------------------------------------------------------------ #
#  ProcessorService — extract_text                                    #
# ------------------------------------------------------------------ #

class ExtractTextServiceTest(SimpleTestCase):
    """extract_text のサービス層ユニットテスト（実 PDF バイト列を使用）"""

    def test_extract_text_from_real_pdf_fixture(self):
        # 実際の PDF バイト列から期待する文字列が抽出できる
        pdf_bytes = _make_pdf_bytes("Service Layer Test")
        result = extract_text(pdf_bytes)
        self.assertIsInstance(result, str)
        self.assertIn("Service", result)

    def test_extract_text_returns_non_empty_string(self):
        # 有効な PDF は空でない文字列を返す
        pdf_bytes = _make_pdf_bytes("Non Empty Content")
        result = extract_text(pdf_bytes)
        self.assertGreater(len(result), 0)


# ------------------------------------------------------------------ #
#  EmbedderService — embed_one                                        #
# ------------------------------------------------------------------ #

class EmbedOneServiceTest(SimpleTestCase):
    """embed_one のサービス層ユニットテスト"""

    def test_embed_one_returns_list_of_length_384(self):
        # embed_one は 384 次元のリストを返す
        result = embed_one("test sentence")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 384)

    def test_embed_one_returns_floats(self):
        # 各要素は float 型である
        result = embed_one("float check")
        for val in result:
            self.assertIsInstance(val, float)


# ------------------------------------------------------------------ #
#  EmbedderService — embed_many                                       #
# ------------------------------------------------------------------ #

class EmbedManyServiceTest(SimpleTestCase):
    """embed_many のサービス層ユニットテスト"""

    def test_embed_many_three_texts_returns_length_3(self):
        # embed_many(['a', 'b', 'c']) は長さ 3 のリストを返す
        result = embed_many(["a", "b", "c"])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    def test_each_embedding_has_384_dimensions(self):
        # 各埋め込みベクトルは 384 次元
        result = embed_many(["a", "b", "c"])
        for vec in result:
            self.assertEqual(len(vec), 384)


# ------------------------------------------------------------------ #
#  SearcherService — search（モックベース、DB 不要）                  #
# ------------------------------------------------------------------ #

class SearchServiceTest(SimpleTestCase):
    """search のサービス層ユニットテスト（Chunk.objects をモック）"""

    def _make_query_vector(self) -> list:
        """テスト用の 384 次元クエリベクトルを生成"""
        return [0.1] * 384

    def _make_mock_queryset(self, return_value=None):
        """モッククエリセットを組み立てるヘルパー"""
        if return_value is None:
            return_value = []
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=return_value)
        return mock_qs

    @patch('kb.services.searcher.Chunk')
    def test_empty_result_returns_empty_list(self, mock_chunk_cls):
        # Chunk テーブルが空の場合、search は [] を返す
        mock_qs = self._make_mock_queryset(return_value=[])
        mock_chunk_cls.objects = mock_qs

        result = search(self._make_query_vector())

        # スライスが呼ばれ、空リストが返ること
        mock_qs.__getitem__.assert_called_once()
        self.assertEqual(list(result), [])

    @patch('kb.services.searcher.Chunk')
    def test_search_returns_mock_chunks(self, mock_chunk_cls):
        # search は Chunk オブジェクトのリストをそのまま返す
        chunk1 = MagicMock()
        chunk2 = MagicMock()
        expected = [chunk1, chunk2]

        mock_qs = self._make_mock_queryset(return_value=expected)
        mock_chunk_cls.objects = mock_qs

        result = search(self._make_query_vector(), top_k=5)
        self.assertEqual(result, expected)

    @patch('kb.services.searcher.Chunk')
    def test_select_related_document_called(self, mock_chunk_cls):
        # select_related('document') が呼ばれること
        mock_qs = self._make_mock_queryset()
        mock_chunk_cls.objects = mock_qs

        search(self._make_query_vector())
        mock_qs.select_related.assert_called_once_with('document')

    @patch('kb.services.searcher.Chunk')
    def test_top_k_slice_applied(self, mock_chunk_cls):
        # [:top_k] のスライスが適用されること
        mock_qs = self._make_mock_queryset()
        mock_chunk_cls.objects = mock_qs

        search(self._make_query_vector(), top_k=3)
        mock_qs.__getitem__.assert_called_once_with(slice(None, 3))
