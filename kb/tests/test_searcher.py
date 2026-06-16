"""
SearcherService のユニットテスト（モックベース、DB不要）
テスト対象：kb/services/searcher.py
  - search(query_vector: list[float], top_k: int = 5) -> list[Chunk]

テスト戦略：
  - Chunk.objects をモックして DB なしで実行
  - select_related, order_by(CosineDistance), [:top_k] のチェーンを検証
"""
from unittest.mock import MagicMock, patch, call
from django.test import SimpleTestCase

from kb.services.searcher import search


class SearchFunctionSignatureTest(SimpleTestCase):
    """search 関数のシグネチャとインターフェイステスト"""

    def test_search_function_exists(self):
        """search 関数がインポート可能であること"""
        self.assertTrue(callable(search))

    def test_search_accepts_query_vector_and_top_k(self):
        """search が query_vector と top_k を受け取ること"""
        import inspect
        sig = inspect.signature(search)
        params = list(sig.parameters.keys())
        self.assertIn('query_vector', params)
        self.assertIn('top_k', params)

    def test_search_top_k_default_is_5(self):
        """top_k のデフォルト値が 5 であること"""
        import inspect
        sig = inspect.signature(search)
        self.assertEqual(sig.parameters['top_k'].default, 5)


class SearchMockTest(SimpleTestCase):
    """Chunk.objects をモックした search 関数の動作テスト"""

    def _make_query_vector(self, size: int = 384) -> list:
        """テスト用の 384 次元クエリベクトルを生成"""
        return [0.1] * size

    @patch('kb.services.searcher.Chunk')
    def test_empty_queryset_returns_empty_list(self, mock_chunk_cls):
        """Chunk テーブルが空のとき [] を返す"""
        # モックチェーンの設定：空のリストを返す
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        result = search([0.1] * 384)
        # スライス [:5] が呼ばれていることを確認
        mock_qs.__getitem__.assert_called_once()

    @patch('kb.services.searcher.Chunk')
    def test_select_related_document_is_called(self, mock_chunk_cls):
        """select_related('document') が呼ばれること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384)

        mock_qs.select_related.assert_called_once_with('document')

    @patch('kb.services.searcher.CosineDistance')
    @patch('kb.services.searcher.Chunk')
    def test_order_by_cosine_distance_is_called(self, mock_chunk_cls, mock_cosine_distance):
        """order_by(CosineDistance('embedding', query_vector)) が呼ばれること"""
        query_vector = [0.1] * 384
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        mock_cosine_distance_instance = MagicMock()
        mock_cosine_distance.return_value = mock_cosine_distance_instance

        search(query_vector)

        # CosineDistance('embedding', query_vector) で初期化されること
        mock_cosine_distance.assert_called_once_with('embedding', query_vector)
        # order_by に CosineDistance インスタンスが渡されること
        mock_qs.order_by.assert_called_once_with(mock_cosine_distance_instance)

    @patch('kb.services.searcher.Chunk')
    def test_top_k_slice_is_applied(self, mock_chunk_cls):
        """[:top_k] のスライスが適用されること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384, top_k=3)

        # slice(None, 3) が呼ばれていることを確認
        mock_qs.__getitem__.assert_called_once_with(slice(None, 3))

    @patch('kb.services.searcher.Chunk')
    def test_default_top_k_is_5(self, mock_chunk_cls):
        """デフォルト top_k=5 の場合 [:5] のスライスが適用されること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384)

        mock_qs.__getitem__.assert_called_once_with(slice(None, 5))

    @patch('kb.services.searcher.Chunk')
    def test_returns_queryset_results(self, mock_chunk_cls):
        """search がクエリセットの結果をそのまま返すこと"""
        # モック Chunk オブジェクトを2つ用意
        chunk1 = MagicMock()
        chunk1.document = MagicMock()
        chunk2 = MagicMock()
        chunk2.document = MagicMock()
        expected = [chunk1, chunk2]

        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=expected)
        mock_chunk_cls.objects = mock_qs

        result = search([0.1] * 384, top_k=5)

        self.assertEqual(result, expected)

    @patch('kb.services.searcher.Chunk')
    def test_method_chain_order(self, mock_chunk_cls):
        """select_related → order_by → スライス の順序でチェーンされること"""
        call_order = []

        mock_qs = MagicMock()

        def mock_select_related(*args, **kwargs):
            call_order.append('select_related')
            return mock_qs

        def mock_order_by(*args, **kwargs):
            call_order.append('order_by')
            return mock_qs

        def mock_getitem(key):
            call_order.append('slice')
            return []

        mock_qs.select_related = mock_select_related
        mock_qs.order_by = mock_order_by
        # __getitem__ は MagicMock の side_effect 経由で設定する
        # （直接関数を代入すると self が渡されてしまうため）
        mock_qs.__getitem__ = MagicMock(side_effect=mock_getitem)
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384)

        self.assertEqual(call_order, ['select_related', 'order_by', 'slice'])
