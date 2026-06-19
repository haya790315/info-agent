"""
ProcessorService: PDF テキスト抽出 + カテゴリ別サイズ分割
"""
import logging

import pymupdf

logger = logging.getLogger("knowledge_base")

# カテゴリ別チャンク設定（chunk_size, overlap）
# 短い項目が連続するドキュメント（resume）は小さく切り詰めることで
# 各チャンクのトピックが絞られ、ベクトル検索の精度が上がる。
# 連続した説明文が多い技術資料（technical）は大きめにして文脈を保つ。
_CHUNK_CONFIG: dict[str, tuple[int, int]] = {
    "resume":    (400,  100),
    "policy":    (500,  120),
    "manual":    (800,  200),
    "technical": (1000, 200),
    "report":    (800,  150),
    "other":     (700,  150),
}
_DEFAULT_CHUNK_CONFIG: tuple[int, int] = (700, 150)


def chunk_config_for_category(category: str) -> tuple[int, int]:
    """カテゴリに対応する (chunk_size, overlap) を返す。未知カテゴリはデフォルト値。"""
    return _CHUNK_CONFIG.get(category, _DEFAULT_CHUNK_CONFIG)


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


def split_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    前置条件：text は文字列（空でも可）、chunk_size は正の整数、overlap < chunk_size
    後置条件：各要素の長さが chunk_size 以下のリストを返す；text が空の場合は []
    オーバーラップにより隣接チャンクの境界部分が重複し、境界をまたぐ情報の欠落を防ぐ
    """
    if not text:
        return []

    stride = max(1, chunk_size - overlap)
    return [text[i: i + chunk_size] for i in range(0, len(text), stride)]
