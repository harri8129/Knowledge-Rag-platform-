from django.db import transaction

from documents.models import (
    Document,
    DocumentChunk,
    DocumentPage,
    ChunkingStatus,
    DocumentStatus,
)
from documents.services.chunking import split_text


def process_document_chunks(document_id:int,chunk_size: int =500 ,chunk_overlap: int = 100):
    """
    Process a document into page-level chunks with full context.
    """

    document = Document.objects.get(id=document_id)

    if document.status != DocumentStatus.READY:
        raise ValueError("Document must be successfully extracted before chunking")

    if document.chunking_status == ChunkingStatus.PROCESSING:
        raise ValueError("Document chunking already in progress")
      
    document.chunking_status = ChunkingStatus.PROCESSING
    document.chunking_error = ""
    document.save(
        update_fields=["chunking_status","chunking_error","updated_at"]
    )

    try:
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
        document.chunking_status = ChunkingStatus.FAILED
        document.chunking_error = str(exc)
        document.save(
            update_fields=[
                "chunking_status",
                "chunking_error",
                "updated_at",
            ]
        )
        raise                    