"""
kbアプリのビュー定義
UploadView: PDF アップロード + ingestion pipeline の調整を担当する
"""
from django.db import transaction
from django.shortcuts import redirect, render
from django.views import View

from kb.forms import UploadForm
from kb.models import Chunk, Document
from kb.services import embedder, processor


class UploadView(View):
    """PDF アップロードと ingestion pipeline を担当するビュー

    GET  /upload/  → アップロードフォームを表示する
    POST /upload/  → バリデーション → ingestion → /documents/{id}/ にリダイレクト
    """

    def get(self, request):
        """アップロードフォームを表示する"""
        form = UploadForm()
        return render(request, "kb/upload.html", {"form": form})

    def post(self, request):
        """PDF ファイルを受け取り、ingestion pipeline を実行する"""
        form = UploadForm(request.POST, request.FILES)

        # バリデーション失敗 → フォームエラーとともに再表示
        if not form.is_valid():
            return render(request, "kb/upload.html", {"form": form})

        file = form.cleaned_data["pdf_file"]

        # ドキュメントレコードを作成し、処理中に更新
        doc = Document.objects.create(
            filename=file.name,
            status=Document.STATUS_PENDING,
        )
        doc.status = Document.STATUS_PROCESSING
        doc.save()

        try:
            # テキスト抽出
            pdf_bytes = file.read()
            text = processor.extract_text(pdf_bytes)

            # 画像型 PDF（テキストなし）は処理不可
            if not text.strip():
                raise ValueError(
                    "PDF に抽出可能なテキストがありません（画像型 PDF の可能性）"
                )

            # 分割 + 埋め込み生成
            chunks = processor.split_into_chunks(text)
            vectors = embedder.embed_many(chunks)

            # Chunk 一括保存とドキュメント更新をアトミックに実行
            with transaction.atomic():
                chunk_objs = [
                    Chunk(document=doc, content=c, embedding=v, position=i)
                    for i, (c, v) in enumerate(zip(chunks, vectors))
                ]
                Chunk.objects.bulk_create(chunk_objs)
                doc.chunk_count = len(chunk_objs)
                doc.status = Document.STATUS_COMPLETE
                doc.save()

        except Exception as e:
            # ingestion 失敗 → エラーメッセージを保存してステータスを failed に更新
            doc.error_message = str(e)
            doc.status = Document.STATUS_FAILED
            doc.save()

        # 成功・失敗どちらの場合もドキュメント詳細ページへリダイレクト
        return redirect("kb:document_detail", pk=doc.pk)
