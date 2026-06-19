"""
kbアプリのURLルーティング設定
各ビューは Task 3.x で実装される
"""
from django.urls import path
from django.views.generic.base import RedirectView

from knowledge_base.api_views import (
    DocumentDetailAPIView,
    DocumentListAPIView,
    SearchAPIView,
)
from knowledge_base.views import DocumentDetailView, SearchView, UploadView

# アプリケーション名前空間（テンプレートで {% url 'kb:...' %} として参照）
app_name = 'knowledge_base'

urlpatterns = [
    # ルートパス（/）はアップロードページへリダイレクトする
    # permanent=False（302）: 将来トップページを変更する可能性を考慮し恒久リダイレクトにはしない
    path('', RedirectView.as_view(pattern_name='knowledge_base:upload', permanent=False), name='home'),
    # Task 3.1: PDF アップロードビュー
    path('upload/', UploadView.as_view(), name='upload'),
    # Task 3.2: ドキュメント詳細ビュー
    path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    # Task 3.3: セマンティック検索ビュー
    path('search/', SearchView.as_view(), name='search'),
    # Task 6.1: ドキュメント一覧 / 詳細 JSON API
    path('api/documents/', DocumentListAPIView.as_view(), name='api_document_list'),
    path('api/documents/<int:pk>/', DocumentDetailAPIView.as_view(), name='api_document_detail'),
    # Task 6.2: セマンティック検索 JSON API
    path('api/search/', SearchAPIView.as_view(), name='api_search'),
]
