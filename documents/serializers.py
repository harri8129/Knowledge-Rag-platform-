from pathlib import Path 
from django.conf import settings
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
            "owner",
            "title",
            "file",
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
            "attempt_count",
            "processing_started_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "owner",
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
            "attempt_count",
            "processing_started_at",
            "created_at",
            "updated_at",
        ]

    def validate_file(self,value):
        allowed_types = {
            ".pdf": "pdf",
            ".txt": "txt",
            ".md": "markdown",
        }
        allowed_mime_types = {
            ".pdf": {"application/pdf"},
            ".txt": {"text/plain"},
            ".md": {"text/markdown", "text/plain"},
        }

        extension = Path(value.name).suffix.lower()

        if extension not in allowed_types:

            allowed = ", ".join(allowed_types.keys())

            raise serializers.ValidationError(
                f"Unsupported file type. Allowed types: {allowed}"
            )

        max_size = settings.MAX_DOCUMENT_UPLOAD_BYTES

        if value.size > max_size:
            raise serializers.ValidationError(
                "File exceeds the configured maximum upload size."
            )

        claimed_mime = getattr(value, "content_type", None)
        if (
            claimed_mime
            and claimed_mime != "application/octet-stream"
            and claimed_mime not in allowed_mime_types[extension]
        ):
            raise serializers.ValidationError(
                "File MIME type does not match its extension."
            )

        try:
            content = value.read()
            value.seek(0)
        except (OSError, AttributeError) as exc:
            raise serializers.ValidationError(
                "Could not validate uploaded file contents."
            ) from exc

        if extension == ".pdf":
            if b"%PDF-" not in content[:1024]:
                raise serializers.ValidationError(
                    "File does not contain a valid PDF header."
                )
        else:
            if b"\x00" in content:
                raise serializers.ValidationError(
                    "Text files must not contain binary data."
                )
            try:
                content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise serializers.ValidationError(
                    "Text files must use UTF-8 encoding."
                ) from exc

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

class RetrievalRequestSerializer(serializers.Serializer):
    query = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=1000,
    )

    top_k = serializers.IntegerField(
        required=False,
        default=5,
        min_value=1,
        max_value=50,
    )

    score_threshold = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0.0,
        max_value=1.0,
    )

    document_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )

    def validate_query(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Query cannot be empty or whitespace"
            )
        return value.strip()


class RAGRequestSerializer(serializers.Serializer):
    query = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=2000,
    )

    top_k = serializers.IntegerField(
        required=False,
        default=5,
        min_value=1,
        max_value=20,
    )

    score_threshold = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0.0,
        max_value=1.0,
    )

    document_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )

    def validate_query(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Query cannot be empty or whitespace."
            )

        return value