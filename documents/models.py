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