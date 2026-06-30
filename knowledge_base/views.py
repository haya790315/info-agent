"""
kbアプリのビュー定義
UploadView: PDF アップロード + ingestion pipeline の調整を担当する
DocumentDetailView: ドキュメント詳細表示を担当する
SearchView: セマンティック検索を担当する
"""

from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from knowledge_base.forms import SearchForm, UploadForm
from knowledge_base.models import Chunk, Document
from knowledge_base.services import embedder, processor, searcher


def _ingest(
    pdf_bytes: bytes, filename: str, category: str
) -> tuple[list[str], list[list[float]]]:
    """抽出→分割→埋め込みを 1 ステップに集約した再利用可能な内部ヘルパー。

    新規アップロードと（将来の）同名置換の双方から利用する。
    破壊的書き込みより前に呼び出すこと（失敗時は例外を送出し、既存データを保護する）。

    Args:
        pdf_bytes: アップロード PDF のバイト列
        filename: ファイル名（埋め込み入力へのコンテキスト注入に使用）
        category: 種別（chunk_size / overlap の決定に使用）

    Returns:
        (chunks, vectors): 長さの等しいタプル。
        chunks は保存用の元チャンクテキスト、vectors はファイル名注入済みテキストの埋め込み。

    Raises:
        ValueError: 抽出可能なテキストが無い場合（画像型 PDF の可能性）。
    """
    # テキスト抽出
    text = processor.extract_text(pdf_bytes)

    # 画像型 PDF（テキストなし）は処理不可
    if not text.strip():
        raise ValueError("PDF に抽出可能なテキストがありません（画像型 PDF の可能性）")

    # 分割 + 埋め込み生成
    # カテゴリに応じた chunk_size / overlap を使用する
    # ファイル名をチャンク内容の前に付与してベクトル化する（コンテキスト注入）
    # DB に保存するのは元のチャンク内容（表示用）、埋め込みだけにファイル名を含める。
    chunk_size, overlap = processor.chunk_config_for_category(category)
    chunks = processor.split_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
    embed_texts = [f"{filename}\n\n{c}" for c in chunks]
    vectors = embedder.embed_many(embed_texts)

    return chunks, vectors


def _replace_document(
    target: Document,
    pdf_bytes: bytes,
    filename: str,
    category: str,
    chunks: list[str],
    vectors: list[list[float]],
) -> None:
    """既存ドキュメントを再利用して内容を原子的に置換する内部ヘルパー。

    既存の行（document id）を保ったまま、旧チャンクを削除して新内容で再構築し、
    種別・チャンク数・ステータス・エラーメッセージ・原本ファイルを更新する。
    さらに同名の他重複ドキュメントを削除し、当該ファイル名を 1 件に収束させる。

    前提条件: chunks / vectors は _ingest により生成済み（破壊的書き込み前に呼ぶこと）。
    後置条件:
        - target.id は不変、旧チャンクは全削除され新チャンクへ置き換わる。
        - 当該 filename に対応する有効 Document は target ただ 1 件（要件 1.4）。
        - 旧物理ファイルは事務 commit 後に削除される。
        - 事務がロールバックした場合、既存ドキュメント・チャンク・原本ファイルは置換前の状態を維持する。

    設計上の要点:
        - 破壊的操作（旧チャンク削除 / 新チャンク作成 / 新ファイル保存と参照切替 /
          メタデータ更新 / 同名重複削除）は単一の transaction.atomic() で原子化する。
        - 旧物理ファイルの削除は **事務内では行わない**。ストレージ削除は非事務的で
          ロールバック不可のため、誤って既存ファイルを消さないよう transaction.on_commit()
          に登録し、commit 成功後にのみ実行する。

    Args:
        target: 置換対象の既存 Document（再利用する行）
        pdf_bytes: 新しい原本 PDF のバイト列
        filename: 新しいファイル名
        category: 新しい種別
        chunks: 保存用チャンクテキスト
        vectors: チャンクに対応する埋め込みベクトル
    """
    # 旧物理ファイル名を参照切替より前に捕捉する（commit 後削除のため）
    # FileField は古いファイルを自動削除しないので明示的に消す必要がある。
    old_file_name = target.file.name if target.file else ""

    # 破壊的操作はすべて単一事務で原子化する（全成 or 全失敗）
    with transaction.atomic():
        # 旧チャンクを全削除（CASCADE ではなく明示削除：行は再利用するため）
        target.chunks.all().delete()

        # 新チャンクを一括作成
        chunk_objs = [
            Chunk(document=target, content=c, embedding=v, position=i)
            for i, (c, v) in enumerate(zip(chunks, vectors))
        ]
        Chunk.objects.bulk_create(chunk_objs)

        # 種別・ファイル名を先に更新する。
        # 原本ファイルの保存先パス（_pdf_upload_path）は instance.category を参照するため、
        # file.save() より前に新しい category を設定しないと旧種別のフォルダに保存されてしまう。
        target.filename = filename
        target.category = category

        # 原本ファイルを新内容で保存し直す（save=False で後段の save() に集約）
        # この時点で target.category は新種別なので pdfs/<新種別>/ 配下に保存される。
        target.file.save(filename, ContentFile(pdf_bytes), save=False)

        # 残りのメタデータを更新して保存
        target.chunk_count = len(chunk_objs)
        target.status = Document.STATUS_COMPLETE
        target.error_message = ""
        # uploaded_at は auto_now_add のため UPDATE では自動更新されない。
        # 置き換え＝再アップロードとみなし、最新の置き換え時刻へ手動で更新する。
        target.uploaded_at = timezone.now()
        target.save()

        # 同名の他重複ドキュメント（target 以外）を削除する（要件 1.4）
        # それらのチャンクは on_delete=CASCADE により連鎖削除される。
        Document.objects.filter(filename=filename).exclude(pk=target.pk).delete()

    # 事務 commit 成功後にのみ旧物理ファイルを削除する（ロールバック安全）
    # 旧ファイル名が新ファイル名と異なる場合のみ削除する
    # （万一同一パスへ上書き保存された場合に新ファイルを消さないため）。
    if old_file_name and old_file_name != target.file.name:
        transaction.on_commit(lambda: target.file.storage.delete(old_file_name))


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
        category = form.cleaned_data.get("category", "")

        # アップロードバイトは一度だけ読み取る（read-once 競合の回避）
        # 同じ bytes を「原本保存」と「テキスト抽出」の両方に使い回す
        pdf_bytes = file.read()

        # 同名判定はファイル名のみで行う（category は判定に含めない、要件 1.3）
        # Meta.ordering = ['-uploaded_at'] により .first() は最新行を返す
        existing = Document.objects.filter(filename=file.name).first()

        # 同名が存在する場合は置換パス（行を再利用し、新規行は作らない、要件 1.1）
        if existing is not None:
            try:
                # 破壊的書き込みより前に抽出/埋め込みを実行（失敗時は既存データ不変）
                # _replace_document は transaction.atomic で原子化済み（タスク 2.3）のため、
                # ここで失敗しても既存ドキュメント・チャンク・原本ファイルは置換前の状態を維持する。
                chunks, vectors = _ingest(pdf_bytes, file.name, category)
                _replace_document(
                    existing, pdf_bytes, file.name, category, chunks, vectors
                )
            except Exception as e:
                # 置換失敗：既存ドキュメントは一切変更しない（status / error_message / chunks 不変、要件 3.1・3.2）。
                # 失敗原因は flash メッセージで通知し、既存ドキュメントの error_message には書き込まない（要件 3.3）。
                messages.error(
                    request,
                    f"ファイルの置き換えに失敗しました: {e}。既存の文書は変更されていません。",
                )
                # 旧・有効内容を保持する既存ドキュメントの詳細ページへリダイレクト（要件 3.3）
                return redirect("knowledge_base:document_detail", pk=existing.pk)

            # 置換成功 → 「既存文書を置き換えた」旨を success flash で通知（要件 4.1）
            messages.success(request, "既存の文書を置き換えました。")
            return redirect("knowledge_base:document_detail", pk=existing.pk)

        # ドキュメントレコードを作成
        doc = Document.objects.create(
            filename=file.name,
            category=category,
            status=Document.STATUS_PENDING,
        )
        # ingestion より前に原本 PDF を保存する
        # → 抽出/埋め込みが失敗（画像型 PDF 等）しても原本は残り、詳細ページから閲覧可能
        doc.file.save(file.name, ContentFile(pdf_bytes), save=False)
        doc.status = Document.STATUS_PROCESSING
        doc.save()

        try:
            # 抽出→分割→埋め込みを再利用ヘルパーに委譲（保存済みの pdf_bytes を再利用）
            # 失敗時は例外を送出する（下の except で failed として記録される）
            chunks, vectors = _ingest(pdf_bytes, file.name, category)

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

            # 新規作成成功（status=COMPLETE）の場合のみ「新規作成」success flash を通知（要件 4.2）
            # except 節に入る失敗時（status=FAILED）には到達しないため、成功時限定で提示される。
            messages.success(request, "新しい文書を作成しました。")

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
        # ハイブリッド検索：ベクトル距離しきい値で絞りつつ、query_text で字面一致も併用する。
        # 人名・固有名詞（例「コウルーヨウ」）はベクトルだけでは拾えないため query_text を渡す。
        # しきい値は環境変数で制御するため、フロント側（フォーム・テンプレート）の変更は不要。
        chunks = searcher.search(
            vector,
            max_distance=settings.SEARCH_MAX_DISTANCE,
            query_text=query,
        )

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
