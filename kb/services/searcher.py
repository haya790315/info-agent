"""
ベクトル類似度検索サービス
pgvector の CosineDistance を用いて top-k チャンクを返す
"""
from pgvector.django import CosineDistance

from kb.models import Chunk


def search(query_vector: list[float], top_k: int = 5) -> list[Chunk]:
    """
    前置条件：query_vector は 384 次元ベクトル、top_k > 0
    後置条件：余弦距離昇順（類似度降順）で ≤ top_k 個の Chunk を返す
              各 Chunk は select_related('document') により document を事前取得済み
              Chunk テーブルが空の場合は [] を返す

    CosineDistance: 0 = 完全一致、2 = 逆方向 → 昇順ソートで類似度の高い順になる
    """
    return (
        Chunk.objects
        .select_related('document')
        .order_by(CosineDistance('embedding', query_vector))[:top_k]
    )
