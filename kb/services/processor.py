"""
ProcessorService: PDF テキスト抽出 + 固定サイズ分割
"""
import logging

import pymupdf

logger = logging.getLogger("kb")


def extract_text(pdf_bytes: bytes) -> str:
    """
    前置条件：pdf_bytes は非空のバイト列
    後置条件：全ページのテキストを結合した文字列を返す；画像型 PDF は '' を返す
    例外：pymupdf の例外はそのまま上位に伝播させる（UploadView でキャッチ）
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        # 全ページのテキストを連結する
        texts = []
        for page in doc:
            texts.append(page.get_text())
        return "".join(texts)
    finally:
        doc.close()


def split_into_chunks(text: str, chunk_size: int = 1000) -> list[str]:
    """
    前置条件：text は文字列（空でも可）、chunk_size は正の整数
    後置条件：各要素の長さが chunk_size 以下のリストを返す；text が空の場合は []
    不変式：全チャンクを順番に結合すると元の text と完全に一致する（文字の損失なし）
    """
    if not text:
        return []

    # 固定文字数でスライスする
    return [text[i: i + chunk_size] for i in range(0, len(text), chunk_size)]
