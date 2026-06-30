"""
ハイブリッド検索サービス
ベクトル類似度（意味検索）と字面一致（キーワード検索）を組み合わせて top-k チャンクを返す。

純粋なベクトル検索は人名・固有名詞・型番などの「キーワード的」なクエリに弱い
（埋め込みモデルが意味を捉えられず、関連チャンクの距離が無関係チャンクと重なる）。
そこで content への部分一致（ILIKE）も併用し、字面一致したチャンクは距離に関わらず
優先採用することで、しきい値だけでは拾えない固有名詞クエリを救う。
"""

from django.db.models import Q
from pgvector.django import CosineDistance

from knowledge_base.models import Chunk


def _dedupe_by_pk(chunks: list[Chunk], top_k: int) -> list[Chunk]:
    """複数の検索結果を順序を保ったまま pk で重複除去し、top_k 件まで返す。

    先に来たものを優先する（呼び出し側が字面一致を先頭に並べることで、
    字面一致を優先採用する）。
    """
    seen: set = set()
    merged: list[Chunk] = []
    for chunk in chunks:
        if chunk.pk in seen:
            continue
        seen.add(chunk.pk)
        merged.append(chunk)
        if len(merged) >= top_k:
            break
    return merged


def search(
    query_vector: list[float],
    top_k: int = 5,
    category: str | None = None,
    max_distance: float | None = None,
    query_text: str | None = None,
) -> list[Chunk]:
    """
    前置条件：query_vector は 384 次元ベクトル、top_k > 0
    後置条件：≤ top_k 個の Chunk を返す（字面一致を先頭に、続いてベクトル距離昇順）
              各 Chunk は select_related('document') により document を事前取得済み
              各 Chunk には distance 属性（コサイン距離）が付与される
              Chunk テーブルが空の場合は [] を返す
              category 指定時は該当種別のドキュメントのみを対象とする
              max_distance 指定時はベクトル検索側で距離がその値を超えるチャンクを除外する
              query_text 指定時は content への部分一致（ILIKE）も併用し、
              字面一致したチャンクは max_distance に関わらず優先採用する（ハイブリッド検索）

    CosineDistance: 0 = 完全一致、2 = 逆方向 → 昇順ソートで類似度の高い順になる
    """

    # annotate で距離を算出フィールド化し、しきい値フィルタ・ソート・表示に使う。
    base = Chunk.objects.select_related("document").annotate(
        distance=CosineDistance("embedding", query_vector)
    )
    if category:
        base = base.filter(document__category=category)

    # --- 字面（キーワード）一致：content または filename に query_text を含む chunk ---
    # 固有名詞・人名の完全一致を狙う。人名は本文に現れずファイル名にだけ存在する場合が
    # あるため、document.filename も対象に含める。
    # 距離が高くても優先採用するため max_distance は適用しない。
    lexical: list[Chunk] = []
    if query_text:
        lexical = list(
            base.filter(
                Q(content__icontains=query_text)
                | Q(document__filename__icontains=query_text)
            ).order_by("distance")[:top_k]
        )

    # --- 意味（ベクトル）検索：距離しきい値で絞り込む ---
    vector_qs = base
    if max_distance is not None:
        vector_qs = vector_qs.filter(distance__lte=max_distance)
    vector_hits = list(vector_qs.order_by("distance")[:top_k])

    # --- マージ：字面一致を先頭に、pk で重複を除きつつ top_k 件まで ---
    return _dedupe_by_pk([*lexical, *vector_hits], top_k)
