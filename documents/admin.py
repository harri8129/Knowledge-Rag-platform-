from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "title",
        "file_type",
        "status",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "file_type",
        "status",
    )

    search_fields = (
        "title",
    )

    ordering = (
        "-created_at",
    )