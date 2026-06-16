"""
learn_ragプロジェクトのWSGI設定
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learn_rag.settings')

application = get_wsgi_application()
