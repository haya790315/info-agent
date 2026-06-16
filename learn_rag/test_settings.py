"""
テスト用 Django 設定ファイル
PostgreSQL が利用できない環境向けに SQLite を使用する
pgvector の VectorField は SQLite では使えないため、モックで対応する
"""
from .settings import *  # noqa: F401, F403

# テスト用に SQLite を使用（DB 不要なテスト環境向け）
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
