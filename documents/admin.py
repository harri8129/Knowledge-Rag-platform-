from django.contrib import admin

from .models import Document, DocumentPage


class DocumentPageInline(admin.TabularInline):
    model = DocumentPage
    extra = 0 
    readonly_fields = ["page_number","content"]
    can_delete = False

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "title",
        "file_type",
        "status",
        "page_count",
        "created_at",
    ]

    list_filter = ["file_type","status",]

    search_fields = ["title"]        
        
    readonly_fields = [
        "file_type",
        "status",
        "page_count",
        "processing_error",
        "created_at",
        "updated_at",
    ]
    inlines = [DocumentPageInline]