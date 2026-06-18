"""
EmbedderService: SentenceTransformer を使ったテキスト埋め込みサービス

モジュールレベルでシングルトンモデルを保持し、
リクエストごとにモデル重みを再ロードしないようにする。

多言語モデル paraphrase-multilingual-MiniLM-L12-v2 を使用する。
日本語クエリで英語文書を、英語クエリで日本語文書を横断検索できる
"""

import os

from sentence_transformers import SentenceTransformer

# 環境変数で上書き可能（既定は多言語 384 次元モデル）
_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

# モジュールレベルシングルトン — 最初のインポート時に一度だけロードする
_model = SentenceTransformer(_MODEL_NAME)


def embed_many(texts: list[str]) -> list[list[float]]:
    """
    複数テキストのベクトル埋め込みを一括生成する。

    前置条件：texts は非空リスト、各要素は非空文字列
    後置条件：texts と等長のリストを返す。各ベクトルは 384 次元の float リスト。
              normalize_embeddings=True により L2 正規化済み（コサイン距離と一致）。

    Args:
        texts: 埋め込み対象のテキストリスト

    Returns:
        各テキストに対応する 384 次元の float リストのリスト
    """
    # numpy 配列を Python ネイティブのリストに変換して返す
    return _model.encode(texts, normalize_embeddings=True).tolist()


def embed_one(text: str) -> list[float]:
    """
    単一テキストのベクトル埋め込みを生成する。

    前置条件：text は非空文字列
    後置条件：384 次元の float リストを返す

    Args:
        text: 埋め込み対象のテキスト

    Returns:
        384 次元の float リスト
    """
    # embed_many を再利用して一貫性を保つ
    return embed_many([text])[0]
