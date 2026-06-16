"""
kbアプリのURLルーティング設定
各ビューは Task 3.x で実装される
"""
from django.urls import path

# アプリケーション名前空間（テンプレートで {% url 'kb:...' %} として参照）
app_name = 'kb'

urlpatterns = [
    # Task 3.1: path('upload/', UploadView.as_view(), name='upload'),
    # Task 3.2: path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    # Task 3.3: path('search/', SearchView.as_view(), name='search'),
]
