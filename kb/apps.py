"""
kbアプリケーションの設定
"""
from django.apps import AppConfig


class KbConfig(AppConfig):
    """PDFナレッジベースアプリの設定クラス"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kb'
    verbose_name = 'PDFナレッジベース'
