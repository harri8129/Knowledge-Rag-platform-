from pydantic._internal._validators import max_length_validator
from pydantic_core.core_schema import model_schema
from django.db import models

class DocumentStatus(models.TextChoices):
    UPLOADED = "UPLOADED","Uploaded"
    PROCESSING = "PROCESSING","Processing"
    READY = "READY","Ready"
    FAILED = "FAILED","Failed"

class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    file_type = models.CharField(max_length=50)
    status = models.CharField(
        max_length = 20,
        choices = DocumentStatus.choices,
        default = DocumentStatus.UPLOADED
    )
    page_count = models.PositiveIntegerField(default=0)
    processing_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True,)
    updated_at = models.DateTimeField(auto_now=True,)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):

        file = self.file

        result = super().delete(*args, **kwargs)

        if file:
            file.delete(save=False)

        return result

class DocumentPage(models.Model):

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    page_number = models.PositiveIntegerField()
    content = models.TextField()

    class Meta:
        ordering = ["page_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document","page_number"],
                name="unique_document_page",
            )
        ]

    def __str__(self):
        return f"{self.document.title} - Page {self.page_number}"