"""
サービス層パッケージ
各モジュールの職責：
  - processor.py : テキスト抽出（PyMuPDF）+ 固定サイズ分割
  - embedder.py  : 埋め込みベクトル生成（sentence-transformers シングルトン）
  - searcher.py  : pgvector CosineDistance による top-k 検索
"""
