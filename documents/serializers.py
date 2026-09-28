from pathlib import Path 
from rest_framework import serializers

from .models import Document



ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".txt": "txt",
    ".md": "markdown",
}

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
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "file_type",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate_file(self,file):

        extension = Path(file.name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:

            allowed = ", ".join(ALLOWED_EXTENSIONS.keys())

            raise serializers.ValidationError(
                f"Unsupported file type. Allowed types: {allowed}"
            )

        max_size = 20 * 1024 * 1024 # 20MB in bytes 

        if file.size > max_size:
            raise serializers.ValidationError(
                "File is too large. Maximum file size is 20MB."
            )   

        return file 

    def create(self,validated_data):

        file = validated_data["file"]
        extension = Path(file.name).suffix.lower()

        validated_data["file_type"] = ALLOWED_EXTENSIONS[extension]

        if not validated_data.get("title"):
            validated_data["title"] = Path(
                file.name
            ).stem
        
        return super().create(validated_data)

