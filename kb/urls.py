"""
kbアプリのURLルーティング設定
各ビューは Task 3.x で実装される
"""
from django.urls import path

from django.http import HttpResponse
from django.views import View

from kb.views import UploadView


class _DocumentDetailStubView(View):
    """Task 3.2 で本実装される DocumentDetailView のスタブ（Task 3.1 のリダイレクト先として必要）"""

    def get(self, request, pk):
        return HttpResponse(f"Document {pk}")


# アプリケーション名前空間（テンプレートで {% url 'kb:...' %} として参照）
app_name = 'kb'

urlpatterns = [
    # Task 3.1: PDF アップロードビュー
    path('upload/', UploadView.as_view(), name='upload'),
    # Task 3.2 で本実装される（現在はスタブ）
    path('documents/<int:pk>/', _DocumentDetailStubView.as_view(), name='document_detail'),
    # Task 3.3: path('search/', SearchView.as_view(), name='search'),
]
