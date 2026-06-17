"""
kbアプリのビュー定義
UploadView: PDF アップロード + ingestion pipeline の調整を担当する
DocumentDetailView: ドキュメント詳細表示を担当する
SearchView: セマンティック検索を担当する
"""
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from knowledge_base.forms import SearchForm, UploadForm
from knowledge_base.models import Chunk, Document
from knowledge_base.services import embedder, processor, searcher


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

        # アップロードバイトは一度だけ読み取る（read-once 競合の回避）
        # 同じ bytes を「原本保存」と「テキスト抽出」の両方に使い回す
        pdf_bytes = file.read()

        # ドキュメントレコードを作成
        doc = Document.objects.create(
            filename=file.name,
            status=Document.STATUS_PENDING,
        )
        # ingestion より前に原本 PDF を保存する
        # → 抽出/埋め込みが失敗（画像型 PDF 等）しても原本は残り、詳細ページから閲覧可能
        doc.file.save(file.name, ContentFile(pdf_bytes), save=False)
        doc.status = Document.STATUS_PROCESSING
        doc.save()

        try:
            # テキスト抽出（保存済みの pdf_bytes を再利用）
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
        return redirect("knowledge_base:document_detail", pk=doc.pk)


class SearchView(View):
    """セマンティック検索ビュー

    GET  /search/  → 空のフォームを表示する
    POST /search/  → クエリをベクトル化して類似チャンクを検索し結果を返す
                     HX-Request ヘッダーが付く場合はパーシャルのみ返す
    """

    def get(self, request):
        # 初回表示：空フォームを渡し、chunks は未設定
        form = SearchForm()
        return render(request, "kb/search.html", {"form": form, "chunks": None})

    def post(self, request):
        # HTMX リクエスト判定
        is_htmx = request.headers.get("HX-Request") == "true"
        form = SearchForm(request.POST)

        if not form.is_valid():
            # バリデーションエラー時：HTMX はパーシャル、通常はフルページ
            ctx = {"form": form, "chunks": None}
            if is_htmx:
                return render(request, "kb/partials/search_results.html", ctx)
            return render(request, "kb/search.html", ctx)

        # クエリをベクトル化して類似チャンクを検索
        query = form.cleaned_data["query"]
        vector = embedder.embed_one(query)
        chunks = searcher.search(vector)

        ctx = {"form": form, "chunks": chunks}
        if is_htmx:
            # HTMX：パーシャルのみ返す（<html> なし）
            return render(request, "kb/partials/search_results.html", ctx)
        # 通常リクエスト：フルページ（パーシャルは search.html 内で include）
        return render(request, "kb/search.html", ctx)


class DocumentDetailView(View):
    """ドキュメント詳細ページを表示するビュー

    GET /documents/{pk}/ → 指定 pk のドキュメント詳細を表示する
    存在しない pk の場合は 404 を返す
    """

    def get(self, request, pk):
        """ドキュメント詳細ページを返す"""
        # 存在しない pk の場合は 404 を返す
        doc = get_object_or_404(Document, pk=pk)
        return render(request, "kb/document_detail.html", {"document": doc})
