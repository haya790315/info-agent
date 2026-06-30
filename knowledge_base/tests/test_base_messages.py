"""
base.html の Django messages 描画区块のテスト
テスト対象：knowledge_base/templates/kb/base.html

このタスクは「闪现メッセージの描画キャリア」を base.html に追加するもの。
実際のメッセージ発火（替换/新建/失败）は後続タスクで views から行う。

検証方針：
base.html を直接テンプレートエンジンで描画し、messages フレームワークが
context processor 経由で提供する `messages` 変数（Message のイテラブル）を
渡したときに、メッセージ本文とそのレベルタグ（success / error）が
描画 HTML に含まれることを確認する。これは本タスクの境界
（base.html テンプレートのみ）内で完結する純粋なテンプレート描画検証。
"""
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import TestCase


class BaseTemplateMessagesRenderTest(TestCase):
    """base.html が messages フレームワークの闪现メッセージを描画する"""

    def _render_with_messages(self, message_list):
        """指定した Message のリストを context に渡して base.html を描画する。

        context processor が提供する `messages` 変数を模して直接注入する。
        """
        return render_to_string("kb/base.html", {"messages": message_list})

    def test_success_message_text_and_tag_rendered(self):
        """success メッセージの本文と success タグが描画される"""
        msg = Message(message_constants.SUCCESS, "既存ドキュメントを置き換えました")
        html = self._render_with_messages([msg])
        self.assertIn("既存ドキュメントを置き換えました", html)
        self.assertIn("success", html)

    def test_error_message_text_and_tag_rendered(self):
        """error メッセージの本文と error タグが描画される"""
        msg = Message(message_constants.ERROR, "処理に失敗しました")
        html = self._render_with_messages([msg])
        self.assertIn("処理に失敗しました", html)
        self.assertIn("error", html)

    def test_no_messages_renders_no_message_block(self):
        """メッセージが無いときは描画しても本文が出ない（回帰防止）"""
        html = self._render_with_messages([])
        self.assertNotIn("既存ドキュメントを置き換えました", html)
        self.assertNotIn("処理に失敗しました", html)
