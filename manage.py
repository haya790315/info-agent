#!/usr/bin/env python
"""Djangoのコマンドラインユーティリティ"""
import os
import sys


def main():
    """管理タスクを実行する"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learn_rag.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Djangoをインポートできませんでした。インストールされているか、"
            "VIRTUAL_ENV が正しく設定されているか確認してください。"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
