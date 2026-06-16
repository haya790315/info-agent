# PostgreSQL の pgvector 拡張を有効化するマイグレーション
# VectorField を含むマイグレーション（0002_initial）より必ず先に実行すること
from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):

    # 依存なし：このマイグレーションがアプリ内で最初に実行される
    dependencies = []

    operations = [
        VectorExtension(),
    ]
