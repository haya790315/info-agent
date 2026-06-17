"""
kbアプリのURLルーティング設定
各ビューは Task 3.x で実装される
"""
from django.urls import path

from knowledge_base.views import DocumentDetailView, SearchView, UploadView

# アプリケーション名前空間（テンプレートで {% url 'kb:...' %} として参照）
app_name = 'knowledge_base'

urlpatterns = [
    # Task 3.1: PDF アップロードビュー
    path('upload/', UploadView.as_view(), name='upload'),
    # Task 3.2: ドキュメント詳細ビュー
    path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    # Task 3.3: セマンティック検索ビュー
    path('search/', SearchView.as_view(), name='search'),
]
