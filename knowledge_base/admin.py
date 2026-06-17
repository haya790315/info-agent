from django.contrib import admin
from .models import Document, Chunk


class ChunkInline(admin.TabularInline):
    model = Chunk
    fields = ('position', 'content')
    readonly_fields = ('position', 'content')
    extra = 0
    show_change_link = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'status', 'chunk_count', 'uploaded_at')
    list_filter = ('status',)
    search_fields = ('filename',)
    readonly_fields = ('filename', 'uploaded_at', 'status', 'chunk_count', 'error_message')
    inlines = [ChunkInline]


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'position', 'short_content')
    list_filter = ('document',)
    search_fields = ('content', 'document__filename')
    readonly_fields = ('document', 'position', 'content')

    def short_content(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
    short_content.short_description = 'content'
