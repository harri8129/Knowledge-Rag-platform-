import logging

from django.db import transaction

from documents.models import (
    Document,
    DocumentChunk,
    DocumentPage,
    ChunkingStatus,
    DocumentStatus,
    IndexingStatus,
)
from documents.services.chunking import split_text
from documents.services.vector_store import delete_document_points

logger = logging.getLogger(__name__)


def process_document_chunks(
    document_id: int,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    *,
    claimed: bool = False,
):
    """
    Process a document into page-level chunks with full context.
    """

    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        valid_document_statuses = {DocumentStatus.READY}
        if claimed:
            valid_document_statuses.add(DocumentStatus.CHUNKING)
        if document.status not in valid_document_statuses:
            raise ValueError(
                "Document must be extracted before chunking."
            )
        if document.chunking_status == ChunkingStatus.PROCESSING:
            raise ValueError("Document chunking already in progress.")
        document.chunking_status = ChunkingStatus.PROCESSING
        document.chunking_error = ""
        document.save(
            update_fields=[
                "chunking_status",
                "chunking_error",
                "updated_at",
            ]
        )

    try:
        if (
            document.indexing_status == IndexingStatus.READY
            or document.indexed_chunk_count > 0
        ):
            delete_document_points(document_id)
            document.indexing_status = IndexingStatus.PENDING
            document.indexed_chunk_count = 0
            document.save(
                update_fields=[
                    "indexing_status",
                    "indexed_chunk_count",
                    "updated_at",
                ]
            )

        pages = DocumentPage.objects.filter(
            document=document,
        ).order_by("page_number")

        chunks_to_create = []
        chunks_index = 0 

        for page in pages:
            for content,start,end in split_text(
                page.content,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ):
                chunks_to_create.append(
                    DocumentChunk(
                        document = document,
                        source_page = page,
                        chunk_index = chunks_index,
                        content = content,
                        start_offset = start,
                        end_offset = end,
                    )
                )
                chunks_index += 1

        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()

            DocumentChunk.objects.bulk_create(chunks_to_create)

            document.chunk_count = len(chunks_to_create)
            document.chunking_status = ChunkingStatus.READY
            document.chunking_error = ""
            document.save(
                update_fields=[
                    "chunk_count",
                    "chunking_status",
                    "chunking_error",
                    "updated_at",
                ]
            )

        return document

    except Exception as exc:
        logger.exception(
            "Document chunking failed",
            extra={"document_id": document_id, "stage": "chunking"},
        )
        Document.objects.filter(pk=document_id).update(
            chunking_status=ChunkingStatus.FAILED,
            chunking_error=str(exc)[:4000],
        )
        raise                    