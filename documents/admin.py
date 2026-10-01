
from django.contrib import admin
from documents.models import Document, DocumentPage, DocumentChunk


class DocumentPageInline(admin.TabularInline):
    model = DocumentPage
    extra = 0
    readonly_fields = ["page_number", "content"]
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "file_type",
        "status",
        "page_count",
        "chunking_status",
        "chunk_count",
        "indexing_status",
        "indexed_chunk_count",
        "created_at",
    ]
    list_filter = [
        "file_type",
        "status",
        "chunking_status",
    ]
    search_fields = ["title"]
    readonly_fields = [
        "file_type",
        "status",
        "page_count",
        "processing_error",
        "chunking_status",
        "chunk_count",
        "chunking_error",
        "indexing_status",
        "indexed_chunk_count",
        "indexing_error",
        "created_at",
        "updated_at",
    ]
    inlines = [DocumentPageInline]


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document",
        "source_page",
        "chunk_index",
        "created_at",
    ]
    list_filter = ["document"]
    search_fields = ["document__title", "content"]
    readonly_fields = [
        "document",
        "source_page",
        "chunk_index",
        "content",
        "start_offset",
        "end_offset",
        "created_at",
    ]
