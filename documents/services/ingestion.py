import logging

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

logger = logging.getLogger(__name__)


def process_document(document_id: int, *, claimed: bool = False) -> Document:
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        if claimed:
            if document.status != DocumentStatus.PROCESSING:
                raise ValueError("Document processing was not claimed.")
        else:
            if document.status in {
                DocumentStatus.PROCESSING,
                DocumentStatus.CHUNKING,
                DocumentStatus.INDEXING,
                DocumentStatus.DELETING,
            }:
                raise ValueError("Document is already being processed.")
            if document.status == DocumentStatus.DELETE_FAILED:
                raise ValueError("Document deletion must be retried first.")
            document.status = DocumentStatus.PROCESSING
            document.processing_started_at = timezone.now()
            document.attempt_count += 1
            document.save(
                update_fields=[
                    "status",
                    "processing_started_at",
                    "attempt_count",
                    "updated_at",
                ]
            )
        document.processing_error = ""
        document.save(
            update_fields=["processing_error", "updated_at"]
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
            if claimed:
                document.status = DocumentStatus.CHUNKING
            else:
                document.processing_started_at = None
            document.page_count = len(pages)
            document.processing_error = ""
            document.save(
                update_fields=[
                    "status",
                    "page_count",
                    "processing_error",
                    "status",
                    "processing_started_at",
                    "updated_at",
                ]
            )

        return document

    except Exception as exc:
        logger.exception(
            "Document extraction failed",
            extra={
                "document_id": document_id,
                "stage": "processing",
            },
        )
        Document.objects.filter(pk=document_id).update(
            status=DocumentStatus.FAILED,
            processing_error=str(exc)[:4000],
            processing_started_at=None,
        )
        raise