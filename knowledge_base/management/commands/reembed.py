"""
reembed: DB のチャンクをリセットし、保存済み PDF ファイルから全ドキュメントを再 ingestion する。

- 対象: Document.file が設定されているドキュメント（PDF ファイルが存在するもの）
- 処理: 既存チャンクを削除 → PDF を読み直し → テキスト抽出 → 分割 → 埋め込み生成 → 保存
- アップロード時と同一ロジック（ファイル名コンテキスト注入済み）で再生成する

使い方:
    make reembed              # 全ドキュメントを再処理
    make reembed -- --dry-run # 対象一覧を確認するだけ（保存なし）
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge_base.models import Chunk, Document
from knowledge_base.services import embedder, processor


class Command(BaseCommand):
    help = "保存済み PDF ファイルからチャンク・ベクトルをリセットして再生成する"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際には保存せず、処理対象のドキュメント一覧だけ表示する",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # file フィールドが設定されているドキュメントのみ対象（PDF ファイルあり）
        docs = list(Document.objects.filter(file__isnull=False).exclude(file=""))
        total = len(docs)
        self.stdout.write(f"対象ドキュメント数: {total}")

        if total == 0:
            self.stdout.write("処理対象がありません。先に PDF をアップロードしてください。")
            return

        if dry_run:
            for doc in docs:
                self.stdout.write(f"  [{doc.id}] {doc.filename}  →  {doc.file.name}")
            self.stdout.write("--dry-run: 保存をスキップします")
            return

        success = 0
        failed = 0

        for doc in docs:
            self.stdout.write(f"\n[{doc.id}] {doc.filename}")
            self.stdout.write(f"  パス: {doc.file.name}")

            # 既存チャンクを削除してステータスをリセット
            deleted_count, _ = doc.chunks.all().delete()
            self.stdout.write(f"  既存チャンク削除: {deleted_count} 件")

            doc.chunk_count = 0
            doc.status = Document.STATUS_PROCESSING
            doc.error_message = ""
            doc.save(update_fields=["chunk_count", "status", "error_message"])

            try:
                # PDF ファイルをファイルシステムから読み込む
                with open(doc.file.path, "rb") as f:
                    pdf_bytes = f.read()

                # テキスト抽出 → カテゴリ別サイズで分割 → ファイル名コンテキスト付きで埋め込み生成
                text = processor.extract_text(pdf_bytes)
                if not text.strip():
                    raise ValueError("PDF に抽出可能なテキストがありません（画像型 PDF の可能性）")

                # アップロード時と同じロジック（カテゴリ別 chunk_size + ファイル名注入）
                chunk_size, overlap = processor.chunk_config_for_category(doc.category)
                chunks = processor.split_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
                embed_texts = [f"{doc.filename}\n\n{c}" for c in chunks]
                vectors = embedder.embed_many(embed_texts)

                with transaction.atomic():
                    chunk_objs = [
                        Chunk(document=doc, content=c, embedding=v, position=i)
                        for i, (c, v) in enumerate(zip(chunks, vectors))
                    ]
                    Chunk.objects.bulk_create(chunk_objs)
                    doc.chunk_count = len(chunk_objs)
                    doc.status = Document.STATUS_COMPLETE
                    doc.save(update_fields=["chunk_count", "status"])

                self.stdout.write(
                    self.style.SUCCESS(f"  → 完了: {len(chunk_objs)} チャンク生成")
                )
                success += 1

            except FileNotFoundError:
                msg = f"PDF ファイルが見つかりません: {doc.file.path}"
                doc.error_message = msg
                doc.status = Document.STATUS_FAILED
                doc.save(update_fields=["error_message", "status"])
                self.stdout.write(self.style.ERROR(f"  → 失敗: {msg}"))
                failed += 1

            except Exception as e:
                doc.error_message = str(e)
                doc.status = Document.STATUS_FAILED
                doc.save(update_fields=["error_message", "status"])
                self.stdout.write(self.style.ERROR(f"  → 失敗: {e}"))
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(f"\n完了: 成功 {success} 件 / 失敗 {failed} 件")
        )
