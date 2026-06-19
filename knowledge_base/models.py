"""
kbアプリのデータモデル定義
Document（ドキュメントメタデータ + ステータス管理）と
Chunk（テキストブロック + 埋め込みベクトル）を定義する
"""
from django.db import models
from pgvector.django import VectorField


def _pdf_upload_path(instance, filename):
    # カテゴリ別サブフォルダに格納する（未設定は uncategorized）
    folder = instance.category if instance.category else "uncategorized"
    return f"pdfs/{folder}/{filename}"


class Document(models.Model):
    """PDFドキュメントのメタデータと処理ステータスを管理するモデル"""

    # ステータス定数（pending → processing → complete | failed の単方向遷移）
    STATUS_PENDING    = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETE   = 'complete'
    STATUS_FAILED     = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING,    '処理待ち'),
        (STATUS_PROCESSING, '処理中'),
        (STATUS_COMPLETE,   '処理完了'),
        (STATUS_FAILED,     '処理失敗'),
    ]

    # ドキュメント種別（エージェントが category フィルタで絞り込むために使用）
    CATEGORY_RESUME    = 'resume'
    CATEGORY_MANUAL    = 'manual'
    CATEGORY_POLICY    = 'policy'
    CATEGORY_TECHNICAL = 'technical'
    CATEGORY_REPORT    = 'report'
    CATEGORY_OTHER     = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_RESUME,    '職歴書・履歴書'),
        (CATEGORY_MANUAL,    'マニュアル・操作手順'),
        (CATEGORY_POLICY,    '規程・ポリシー'),
        (CATEGORY_TECHNICAL, '技術資料'),
        (CATEGORY_REPORT,    'レポート・報告書'),
        (CATEGORY_OTHER,     'その他'),
    ]

    filename      = models.CharField(max_length=255)
    # ドキュメント種別（未設定=空文字、エージェントの絞り込み検索に使用）
    category      = models.CharField(
        max_length=64,
        choices=CATEGORY_CHOICES,
        blank=True,
        default='',
    )
    # アップロードされた原本 PDF（MEDIA_ROOT/pdfs/<category>/ に保存）
    # blank/null 許可：既存行や原本未保存のケースでも破綻しないようにする
    file          = models.FileField(upload_to=_pdf_upload_path, blank=True, null=True)
    uploaded_at   = models.DateTimeField(auto_now_add=True)
    status        = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    # エラー発生時のメッセージ（status=failed のときのみ非空）
    error_message = models.TextField(blank=True, default='')
    # ingestion完了後に一括更新されるチャンク数
    chunk_count   = models.IntegerField(default=0)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.filename} ({self.status})"


class Chunk(models.Model):
    """テキストブロックと384次元の埋め込みベクトルを保持するモデル"""

    # Documentが削除されたときにChunkも連鎖削除する
    document  = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks',
    )
    content   = models.TextField()
    # all-MiniLM-L6-v2 の出力次元数に合わせた 384 次元の埋め込みベクトル
    embedding = VectorField(dimensions=384)
    position  = models.IntegerField()  # ドキュメント内の0始まりの順序

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"Chunk {self.position} of {self.document.filename}"
