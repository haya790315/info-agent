"""
ProcessorService のユニットテスト
テスト対象：kb/services/processor.py
  - extract_text(pdf_bytes: bytes) -> str
  - split_into_chunks(text: str, chunk_size: int = 1000) -> list[str]
"""
import fitz  # PyMuPDF
from django.test import SimpleTestCase

from kb.services.processor import extract_text, split_into_chunks


def _make_pdf_bytes(text: str = "Hello World") -> bytes:
    """テスト用の最小 PDF バイト列を生成するヘルパー"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class SplitIntoChunksTest(SimpleTestCase):
    """split_into_chunks の単体テスト"""

    def test_empty_string_returns_empty_list(self):
        """空文字列を渡すと [] が返る"""
        result = split_into_chunks("")
        self.assertEqual(result, [])

    def test_1500_chars_returns_two_chunks(self):
        """1500 文字の文字列は 2 つのチャンクに分割される"""
        text = "a" * 1500
        result = split_into_chunks(text)
        self.assertEqual(len(result), 2)

    def test_chunks_joined_equal_original_text(self):
        """全チャンクを結合すると元のテキストと一致する（文字の損失なし）"""
        text = "x" * 2500
        chunks = split_into_chunks(text)
        self.assertEqual("".join(chunks), text)

    def test_exactly_1000_chars_returns_one_chunk(self):
        """ちょうど 1000 文字の文字列は 1 チャンクで返る（境界値テスト）"""
        text = "x" * 1000
        result = split_into_chunks(text)
        self.assertEqual(len(result), 1)

    def test_chunks_invariant_with_custom_chunk_size(self):
        """カスタム chunk_size でもチャンク結合が元テキストと一致する"""
        text = "abc" * 700  # 2100 文字
        chunks = split_into_chunks(text, chunk_size=500)
        self.assertEqual("".join(chunks), text)
        # 全チャンクが chunk_size 以下であることを確認
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 500)


class ExtractTextTest(SimpleTestCase):
    """extract_text の単体テスト"""

    def test_extract_text_from_valid_pdf(self):
        """有効な PDF から非空文字列が返る"""
        pdf_bytes = _make_pdf_bytes("Hello World")
        result = extract_text(pdf_bytes)
        self.assertIsInstance(result, str)
        self.assertIn("Hello", result)

    def test_extract_text_returns_string(self):
        """extract_text は常に str を返す"""
        pdf_bytes = _make_pdf_bytes("Test content for extraction")
        result = extract_text(pdf_bytes)
        self.assertIsInstance(result, str)

    def test_invalid_bytes_raises_exception(self):
        """無効なバイト列は例外を投げる"""
        with self.assertRaises(Exception):
            extract_text(b"not a pdf")
