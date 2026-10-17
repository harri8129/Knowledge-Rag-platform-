import logging

from django.db import transaction
from django.utils import timezone

from documents.models import Document, DocumentStatus
from documents.services.vector_store import delete_document_points

logger = logging.getLogger(__name__)


class DocumentDeletionError(RuntimeError):
    pass


def delete_document(document_id: int) -> None:
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        if document.status in {
            DocumentStatus.PROCESSING,
            DocumentStatus.CHUNKING,
            DocumentStatus.INDEXING,
            DocumentStatus.DELETING,
        }:
            raise ValueError("Document has an operation in progress.")
        if document.status not in {
            DocumentStatus.DELETE_FAILED,
            DocumentStatus.UPLOADED,
            DocumentStatus.READY,
            DocumentStatus.FAILED,
        }:
            raise ValueError("Document cannot be deleted in its current state.")
        document.status = DocumentStatus.DELETING
        document.processing_error = ""
        document.processing_started_at = timezone.now()
        document.save(
            update_fields=[
                "status",
                "processing_error",
                "processing_started_at",
                "updated_at",
            ]
        )

    try:
        delete_document_points(document_id)
    except Exception as exc:
        logger.exception(
            "Qdrant cleanup failed during document deletion",
            extra={"document_id": document_id, "stage": "deletion"},
        )
        Document.objects.filter(pk=document_id).update(
            status=DocumentStatus.DELETE_FAILED,
            processing_error=str(exc)[:4000],
            processing_started_at=None,
        )
        raise DocumentDeletionError(
            "Document deletion failed during vector cleanup."
        ) from exc

    try:
        with transaction.atomic():
            document = Document.objects.select_for_update().get(
                pk=document_id
            )
            if document.status != DocumentStatus.DELETING:
                raise DocumentDeletionError(
                    "Document deletion state changed unexpectedly."
                )
            document.delete()
    except Exception as exc:
        logger.exception(
            "Database deletion failed after Qdrant cleanup",
            extra={"document_id": document_id, "stage": "deletion"},
        )
        Document.objects.filter(pk=document_id).update(
            status=DocumentStatus.DELETE_FAILED,
            processing_error=str(exc)[:4000],
            processing_started_at=None,
        )
        if isinstance(exc, DocumentDeletionError):
            raise
        raise DocumentDeletionError(
            "Document deletion failed after vector cleanup."
        ) from exc
