from django.db import transaction
from django.utils import timezone

from documents.models import (
Document,
DocumentPage,
DocumentStatus
)
from documents.services.extraction import (
extract_document
)

def process_document(document_id):
    document = Document.objects.get(id=document_id)

    if document.status == DocumentStatus.PROCESSING:
        raise ValueError("Document is already processing.")

    document.status = DocumentStatus.PROCESSING
    document.processing_error = ""
    document.save(
        update_fields=["status","processing_error","updated_at"]
    )

    try:
        with document.file.open("rb") as file_obj:
            pages = extract_document(
                file_obj,
                document.file_type,
            )

        with transaction.atomic():
            # Remove any OLD extraction results so that 
            # reprocessing does not duplicate page record 
            DocumentPage.objects.filter(
                document=document
            ).delete()

            DocumentPage.objects.bulk_create([
                DocumentPage(
                    document=document,
                    page_number=page["page_number"],
                    content=page["content"],
                )
                for page in pages
            ])

            document.status = DocumentStatus.READY
            document.page_count = len(pages)
            document.processing_error = ""
            document.save(
                update_fields=[
                    "status",
                    "page_count",
                    "processing_error",
                    "updated_at",
                ]
            )

        return document

    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.processing_error = str(exc)
        document.save(
            update_fields=[
                'status',
                "processing_error",
                "updated_at",
            ]
        )
        raise
    
      