from pathlib import Path 
from rest_framework import serializers

from .models import Document,DocumentPage,DocumentChunk


class DocumentSerializer(serializers.ModelSerializer):

    title = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )

    class Meta:
        model = Document 

        fields = [
            "id",
            "title",
            "file",
            "file_type",
            "status",
            "page_count",
            "processing_error",
            "indexing_status",
            "indexed_chunk_count",
            "indexing_error",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "file_type",
            "status",
            "page_count",
            "processing_error",
            "indexing_status",
            "indexed_chunk_count",
            "indexing_error",
            "created_at",
            "updated_at",
        ]

    def validate_file(self,value):

        allowed_types = {
            ".pdf": "pdf",
            ".txt": "txt",
            ".md": "markdown",
        }

        extension = Path(value.name).suffix.lower()

        if extension not in allowed_types:

            allowed = ", ".join(allowed_types.keys())

            raise serializers.ValidationError(
                f"Unsupported file type. Allowed types: {allowed}"
            )

        max_size = 20 * 1024 * 1024 # 20MB in bytes 

        if value.size > max_size:
            raise serializers.ValidationError(
                "File is too large. Maximum file size is 20MB."
            )   

        return value 

    def create(self,validated_data):
        uploaded_file = validated_data["file"]

        extension = Path(uploaded_file.name).suffix.lower()

        file_types = {
            ".pdf": "pdf",
            ".txt": "txt",
            ".md": "markdown",
        }

        validated_data["file_type"] = file_types[extension]

        if not validated_data.get("title","").strip():
            validated_data["title"] = Path(
                uploaded_file.name
            ).stem
        
        return super().create(validated_data)

class DocumentPageSerializer(serializers.ModelSerializer):

    class Meta:
        model = DocumentPage
        fields = [
            "id",
            "document",
            "page_number",
            "content",
        ]
        read_only_fields = fields

class DocumentChunkSerializer(serializers.ModelSerializer):
    page_number = serializers.IntegerField(
        source="source_page.page_number",
        read_only=True,
    )

    class Meta:
        model = DocumentChunk
        fields = [
            "id",
            "document",
            "source_page",
            "page_number",
            "chunk_index",
            "content",
            "start_offset",
            "end_offset",
            "created_at",
        ]
        read_only_fields = fields