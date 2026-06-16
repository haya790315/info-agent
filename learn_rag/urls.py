"""
learn_ragプロジェクトのURLルーティング設定
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # kbアプリのURLをインクルード（ルートパスにマウント）
    path('', include('kb.urls')),
]
