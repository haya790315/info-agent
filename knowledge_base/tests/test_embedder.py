"""
EmbedderService のユニットテスト
テスト対象：kb/services/embedder.py
  - embed_one(text: str) -> list[float]
  - embed_many(texts: list[str]) -> list[list[float]]
"""
from django.test import SimpleTestCase

from knowledge_base.services.embedder import embed_one, embed_many


class EmbedOneTest(SimpleTestCase):
    """embed_one の単体テスト"""

    def test_embed_one_returns_list_of_length_384(self):
        """embed_one('test') は長さ 384 のリストを返す"""
        result = embed_one("test")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 384)

    def test_embed_one_returns_list_of_floats(self):
        """embed_one('test') の各要素は float 型"""
        result = embed_one("test")
        for val in result:
            self.assertIsInstance(val, float)

    def test_embed_one_different_texts_return_different_vectors(self):
        """異なるテキストは異なるベクトルを返す（定数ベクトルでないことを確認）"""
        v1 = embed_one("hello")
        v2 = embed_one("world")
        self.assertNotEqual(v1, v2)


class EmbedManyTest(SimpleTestCase):
    """embed_many の単体テスト"""

    def test_embed_many_returns_list_of_correct_length(self):
        """embed_many(['a', 'b', 'c']) は長さ 3 のリストを返す"""
        result = embed_many(["a", "b", "c"])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    def test_embed_many_consistent_with_embed_one(self):
        """embed_many(['a']) の結果は [embed_one('a')] と一致する（一貫性チェック）"""
        result_many = embed_many(["a"])
        result_one = [embed_one("a")]
        self.assertEqual(result_many, result_one)
