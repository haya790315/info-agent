"""
kbアプリの読み取り専用 JSON API ビュー
外部編排層（typescript-agent）が検索層をプログラムから呼び出すためのエンドポイント群。
Django 組み込みの View + JsonResponse を使用し、DRF は導入しない。
全レスポンスは application/json（HTML ラップなし）。
"""
import json

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from knowledge_base.forms import SearchForm
from knowledge_base.models import Document
from knowledge_base.services import embedder, searcher


# --- シリアライズ補助関数（モジュールレベル） ---

def _file_url(doc, request):
    """原本ファイルの絶対 URL を返す。未保存なら None。

    後置条件：doc.file が真 → request.build_absolute_uri(doc.file.url)；そうでなければ None
    （TS Agent / ブラウザがそのまま開けるよう絶対 URL 化する）
    """
    if doc.file:
        return request.build_absolute_uri(doc.file.url)
    return None


def _document_dict(doc, request):
    """Document → JSON dict 変換"""
    return {
        "id": doc.id,
        "filename": doc.filename,
        "category": doc.category,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "uploaded_at": doc.uploaded_at.isoformat(),
        "error_message": doc.error_message,
        "file_url": _file_url(doc, request),
    }


def _chunk_dict(chunk, request):
    """Chunk → JSON dict 変換

    searcher が annotate 済みの distance（コサイン距離）と select_related 済みの
    document をそのまま再利用する。distance を Python 側で再計算しない
    （= 埋め込みベクトルの再読込・内積計算を避ける）。
    """
    distance = getattr(chunk, "distance", None)
    return {
        "content": chunk.content,
        "filename": chunk.document.filename,
        "category": chunk.document.category,
        "document_id": chunk.document_id,
        "file_url": _file_url(chunk.document, request),
        # コサイン距離（関連度の指標、小さいほど関連）。searcher の annotate 値を再利用
        "distance": round(distance, 4) if distance is not None else None,
    }


# --- API ビュー ---

class DocumentListAPIView(View):
    """GET /api/documents/ → 全ドキュメントの JSON 配列"""

    def get(self, request):
        docs = Document.objects.all()  # Meta.ordering: -uploaded_at
        return JsonResponse(
            {"documents": [_document_dict(d, request) for d in docs]}
        )


class DocumentDetailAPIView(View):
    """GET /api/documents/<pk>/ → ドキュメント詳細 JSON（存在しなければ 404）"""

    def get(self, request, pk) -> JsonResponse:
        try:
            doc = Document.objects.get(pk=pk)
        except Document.DoesNotExist:
            return JsonResponse(
                {"error": "ドキュメントが見つかりません。"}, status=404
            )
        return JsonResponse(_document_dict(doc, request))


@method_decorator(csrf_exempt, name='dispatch')
class SearchAPIView(View):
    """POST /api/search/ → セマンティック検索の JSON 結果

    硬い契約：Content-Type: application/json、body は {"query": str}。
    サーバ間呼び出し（セッション認証なし）のため csrf_exempt。
    """

    def post(self, request):
        # JSON body を解析。不正 JSON / query 欠落は空クエリ扱いで 400 へ
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            payload = {}
        query    = payload.get("query", "")    if isinstance(payload, dict) else ""
        category = payload.get("category", "") if isinstance(payload, dict) else ""

        # 既存の SearchForm の検証ロジックを再利用（空クエリは無効）
        form = SearchForm({"query": query})
        if not form.is_valid():
            # 検証失敗 → embedder / searcher を呼ばずに 400
            return JsonResponse(
                {"error": "検索クエリを入力してください。"}, status=400
            )

        # 検証通過 → クエリをベクトル化して類似チャンクを検索（top_k=5）
        # category が空文字のときはフィルタなし（全種別対象）
        # 関連性しきい値（settings.SEARCH_MAX_DISTANCE）はサーバ側で一元管理する。
        # query_text を渡してハイブリッド検索（字面一致併用）を有効化する。
        cleaned_query = form.cleaned_data["query"]
        vector = embedder.embed_one(cleaned_query)
        chunks = searcher.search(
            vector,
            top_k=5,
            category=category or None,
            max_distance=settings.SEARCH_MAX_DISTANCE,
            query_text=cleaned_query,
        )
        # 各チャンクには searcher が distance を annotate 済み。
        # Chunk テーブルが空の場合は results=[]（200、エラーではない）
        return JsonResponse(
            {"results": [_chunk_dict(c, request) for c in chunks]}
        )
