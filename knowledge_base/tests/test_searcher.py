"""
SearcherService のユニットテスト（モックベース、DB不要）
テスト対象：kb/services/searcher.py
  - search(query_vector: list[float], top_k: int = 5) -> list[Chunk]

テスト戦略：
  - Chunk.objects をモックして DB なしで実行
  - select_related, annotate(CosineDistance), order_by('distance'), [:top_k] のチェーンを検証
"""
from unittest.mock import MagicMock, patch, call
from django.db.models import Q
from django.test import SimpleTestCase

from knowledge_base.services.searcher import search, _dedupe_by_pk


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

    @patch('knowledge_base.services.searcher.Chunk')
    def test_empty_queryset_returns_empty_list(self, mock_chunk_cls):
        """Chunk テーブルが空のとき [] を返す"""
        # モックチェーンの設定：空のリストを返す
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        result = search([0.1] * 384)
        # スライス [:5] が呼ばれていることを確認
        mock_qs.__getitem__.assert_called_once()

    @patch('knowledge_base.services.searcher.Chunk')
    def test_select_related_document_is_called(self, mock_chunk_cls):
        """select_related('document') が呼ばれること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384)

        mock_qs.select_related.assert_called_once_with('document')

    @patch('knowledge_base.services.searcher.CosineDistance')
    @patch('knowledge_base.services.searcher.Chunk')
    def test_annotate_cosine_distance_and_order_by(self, mock_chunk_cls, mock_cosine_distance):
        """annotate(distance=CosineDistance(...)) と order_by('distance') が呼ばれること"""
        query_vector = [0.1] * 384
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        mock_cosine_distance_instance = MagicMock()
        mock_cosine_distance.return_value = mock_cosine_distance_instance

        search(query_vector)

        # CosineDistance('embedding', query_vector) で初期化されること
        mock_cosine_distance.assert_called_once_with('embedding', query_vector)
        # annotate に distance=CosineDistance インスタンスが渡されること
        mock_qs.annotate.assert_called_once_with(distance=mock_cosine_distance_instance)
        # order_by には算出フィールド名 'distance' が渡されること
        mock_qs.order_by.assert_called_once_with('distance')

    @patch('knowledge_base.services.searcher.Chunk')
    def test_top_k_slice_is_applied(self, mock_chunk_cls):
        """[:top_k] のスライスが適用されること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384, top_k=3)

        # slice(None, 3) が呼ばれていることを確認
        mock_qs.__getitem__.assert_called_once_with(slice(None, 3))

    @patch('knowledge_base.services.searcher.Chunk')
    def test_default_top_k_is_5(self, mock_chunk_cls):
        """デフォルト top_k=5 の場合 [:5] のスライスが適用されること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384)

        mock_qs.__getitem__.assert_called_once_with(slice(None, 5))

    @patch('knowledge_base.services.searcher.Chunk')
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
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=expected)
        mock_chunk_cls.objects = mock_qs

        result = search([0.1] * 384, top_k=5)

        self.assertEqual(result, expected)

    @patch('knowledge_base.services.searcher.Chunk')
    def test_max_distance_applies_filter(self, mock_chunk_cls):
        """max_distance 指定時は distance__lte でフィルタが掛かること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384, max_distance=0.5)

        mock_qs.filter.assert_called_once_with(distance__lte=0.5)

    @patch('knowledge_base.services.searcher.Chunk')
    def test_no_max_distance_skips_filter(self, mock_chunk_cls):
        """max_distance 未指定（None）時は filter を呼ばないこと"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384)

        mock_qs.filter.assert_not_called()

    @patch('knowledge_base.services.searcher.Chunk')
    def test_method_chain_order(self, mock_chunk_cls):
        """select_related → annotate → order_by → スライス の順序でチェーンされること"""
        call_order = []

        mock_qs = MagicMock()

        def mock_select_related(*args, **kwargs):
            call_order.append('select_related')
            return mock_qs

        def mock_annotate(*args, **kwargs):
            call_order.append('annotate')
            return mock_qs

        def mock_order_by(*args, **kwargs):
            call_order.append('order_by')
            return mock_qs

        def mock_getitem(key):
            call_order.append('slice')
            return []

        mock_qs.select_related = mock_select_related
        mock_qs.annotate = mock_annotate
        mock_qs.order_by = mock_order_by
        # __getitem__ は MagicMock の side_effect 経由で設定する
        # （直接関数を代入すると self が渡されてしまうため）
        mock_qs.__getitem__ = MagicMock(side_effect=mock_getitem)
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384)

        # max_distance 未指定なので filter は挟まらない
        self.assertEqual(call_order, ['select_related', 'annotate', 'order_by', 'slice'])


class HybridSearchTest(SimpleTestCase):
    """ハイブリッド検索（字面一致併用）の動作テスト"""

    @patch('knowledge_base.services.searcher.Chunk')
    def test_query_text_triggers_lexical_filter(self, mock_chunk_cls):
        """query_text 指定時は content/filename への字面フィルタが呼ばれること"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384, max_distance=0.8, query_text='コウルーヨウ')

        # 字面一致は content または filename の OR 条件（Q）で呼ばれる
        expected_q = (
            Q(content__icontains='コウルーヨウ')
            | Q(document__filename__icontains='コウルーヨウ')
        )
        mock_qs.filter.assert_any_call(expected_q)
        # ベクトル距離しきい値フィルタも呼ばれる
        mock_qs.filter.assert_any_call(distance__lte=0.8)

    @patch('knowledge_base.services.searcher.Chunk')
    def test_no_query_text_skips_lexical_filter(self, mock_chunk_cls):
        """query_text 未指定時は字面フィルタ（Q による位置引数）を呼ばないこと"""
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_chunk_cls.objects = mock_qs

        search([0.1] * 384, max_distance=0.8)

        # 字面フィルタは Q を位置引数で渡す。query_text なしでは位置引数呼び出しが無い
        for c in mock_qs.filter.call_args_list:
            self.assertEqual(c.args, ())


class DedupeByPkTest(SimpleTestCase):
    """_dedupe_by_pk ヘルパーの単体テスト（DB不要）"""

    def _chunk(self, pk):
        return MagicMock(pk=pk)

    def test_preserves_order_and_removes_duplicates(self):
        """順序を保ちつつ pk 重複を除去する（先勝ち）"""
        a, b, c = self._chunk(1), self._chunk(2), self._chunk(3)
        b_dup = self._chunk(2)  # b と同じ pk
        result = _dedupe_by_pk([a, b, b_dup, c], top_k=5)
        self.assertEqual([x.pk for x in result], [1, 2, 3])

    def test_first_occurrence_wins(self):
        """重複時は先に現れたインスタンスを残す（字面一致を優先）"""
        lexical = self._chunk(7)
        vector_dup = self._chunk(7)
        result = _dedupe_by_pk([lexical, vector_dup], top_k=5)
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], lexical)

    def test_caps_at_top_k(self):
        """top_k 件で打ち切る"""
        chunks = [self._chunk(i) for i in range(10)]
        result = _dedupe_by_pk(chunks, top_k=3)
        self.assertEqual(len(result), 3)
        self.assertEqual([x.pk for x in result], [0, 1, 2])

    def test_empty_input(self):
        """空入力は空リストを返す"""
        self.assertEqual(_dedupe_by_pk([], top_k=5), [])
