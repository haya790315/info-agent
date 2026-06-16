# Document と Chunk テーブルを作成するマイグレーション
# pgvector 拡張が有効化された 0001_vector_extension の後に実行すること
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from pgvector.django import VectorField


class Migration(migrations.Migration):

    # 0001_vector_extension が完了してから実行する（VectorField に必要）
    dependencies = [
        ('kb', '0001_vector_extension'),
    ]

    operations = [
        # Document テーブル：PDFドキュメントのメタデータとステータスを管理
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending',    '処理待ち'),
                        ('processing', '処理中'),
                        ('complete',   '処理完了'),
                        ('failed',     '処理失敗'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                # status=failed のときのみ非空となるエラーメッセージ
                ('error_message', models.TextField(blank=True, default='')),
                # ingestion 完了後に一括更新されるチャンク数
                ('chunk_count', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['-uploaded_at'],
            },
        ),
        # Chunk テーブル：テキストブロックと 384 次元の埋め込みベクトルを保持
        migrations.CreateModel(
            name='Chunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Document が削除されたときに連鎖削除される外部キー
                ('document', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chunks',
                    to='kb.document',
                )),
                ('content', models.TextField()),
                # all-MiniLM-L6-v2 の出力次元数 384 に合わせた pgvector フィールド
                ('embedding', VectorField(dimensions=384)),
                # ドキュメント内の 0 始まりの順序
                ('position', models.IntegerField()),
            ],
            options={
                'ordering': ['position'],
            },
        ),
    ]
