"""
info_agentプロジェクトのURLルーティング設定
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # kbアプリのURLをインクルード（ルートパスにマウント）
    path("", include("knowledge_base.urls")),
]

# 開発環境（DEBUG=True）でのみ、保存した原本 PDF を MEDIA_URL 経由で配信する
# 本番では Web サーバ側で配信する想定のため、ここでは追加しない
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
