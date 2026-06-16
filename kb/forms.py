"""
kbアプリのフォーム定義
PDF アップロードバリデーションを担当する
"""
from django import forms

# 最大ファイルサイズ（10MB）
MAX_FILE_SIZE = 10_485_760  # 10MB in bytes


class UploadForm(forms.Form):
    """PDF アップロードフォーム

    バリデーション条件:
    - content_type が application/pdf であること
    - ファイルサイズが 0 バイトより大きいこと
    - ファイルサイズが 10MB 以下であること
    """

    pdf_file = forms.FileField(
        label="PDF ファイル",
        help_text="10MB 以下の PDF ファイルをアップロードしてください",
    )

    def clean_pdf_file(self):
        """PDF ファイルのバリデーション処理"""
        file = self.cleaned_data.get("pdf_file")
        if file is None:
            return file

        # ファイルサイズ > 0 チェック（空ファイル拒否）
        if file.size == 0:
            raise forms.ValidationError("空のファイルはアップロードできません。")

        # ファイルサイズ ≤ 10MB チェック
        if file.size > MAX_FILE_SIZE:
            raise forms.ValidationError(
                "ファイルサイズが上限（10MB）を超えています。"
            )

        # content_type チェック（PDF のみ許可）
        if file.content_type != "application/pdf":
            raise forms.ValidationError(
                "PDF ファイルのみアップロードできます。"
            )

        return file
