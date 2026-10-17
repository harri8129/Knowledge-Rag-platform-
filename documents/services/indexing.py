import logging
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from documents.models import (
    Document,
    DocumentChunk,
    ChunkingStatus,
    IndexingStatus,
    DocumentStatus,
)
from documents.services.embeddings import embed_texts
from documents.services.vector_store import (
    get_qdrant_client,
    ensure_collection,
    upsert_points,
    delete_points,
    get_document_point_ids,
)
from qdrant_client import models

logger = logging.getLogger(__name__)


def stable_point_id(chunk_id:int) -> str:
    """ 
    Produce a deterministic UUID so retries update the same 
    Qdrant point instead of creating duplicates.
    """
    return str(uuid5(NAMESPACE_URL,
            f"rag-knowledge-engine:chunk:{chunk_id}",                    )
    )

def process_document_indexing(
    document_id: int,
    *,
    claimed: bool = False,
) -> Document:
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        if document.chunking_status != ChunkingStatus.READY:
            raise ValueError("Document must be chunked before indexing.")
        if document.indexing_status == IndexingStatus.PROCESSING:
            raise ValueError("Document is already being indexed.")
        if claimed:
            if document.status != DocumentStatus.INDEXING:
                raise ValueError("Document indexing was not claimed.")
        else:
            if document.status != DocumentStatus.READY:
                raise ValueError(
                    "Document must be ready before indexing."
                )
            document.status = DocumentStatus.INDEXING
            document.processing_started_at = timezone.now()
        document.indexing_status = IndexingStatus.PROCESSING
        document.indexing_error = ""
        document.save(
            update_fields=[
                "status",
                "processing_started_at",
                "indexing_status",
                "indexing_error",
                "updated_at",
            ]
        )

    client = None
    try:
        client = get_qdrant_client()
        ensure_collection(client)

        old_point_ids = set(
            get_document_point_ids(client, document.pk)
        )
        current_point_ids = set()

        chunks = (
            DocumentChunk.objects
            .filter(document=document)
            .select_related("source_page", "document")
            .order_by("chunk_index")
        )
        if not chunks.exists():
            raise ValueError("Document has no chunks to index.")

        batch_size = settings.EMBEDDING_BATCH_SIZE
        indexed_count = 0

        chunk_iterator = iter(chunks.iterator(chunk_size=batch_size))

        while True:
            batch: list[DocumentChunk] = []
            for _ in range(batch_size):
                try:
                    batch.append(next(chunk_iterator))
                except StopIteration:
                    break

            if not batch:
                break

            texts = [chunk.content for chunk in batch]
            vectors = embed_texts(texts)

            points = []

            for chunk, vector in zip(batch, vectors):
                point_id = stable_point_id(chunk.id)
                current_point_ids.add(point_id)

                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "document_id": document.pk,
                            "document_title": document.title,
                            "chunk_id": chunk.id,
                            "chunk_index": chunk.chunk_index,
                            "page_number": chunk.source_page.page_number,
                            "content": chunk.content,
                        },
                    )
                )

            upsert_points(client, points)
            indexed_count += len(points)

            Document.objects.filter(pk=document.pk).update(
                indexed_chunk_count=indexed_count
            )

        # Delete points from older chunk sets only after all
        # current points have been upserted successfully.
        stale_ids = old_point_ids - current_point_ids

        if stale_ids:
            delete_points(client, list(stale_ids))

        document.refresh_from_db()
        document.indexed_chunk_count = indexed_count
        document.indexing_status = IndexingStatus.READY
        document.indexing_error = ""
        document.status = DocumentStatus.READY
        document.processing_started_at = None
        document.save(
            update_fields=[
                "status",
                "processing_started_at",
                "indexed_chunk_count",
                "indexing_status",
                "indexing_error",
                "updated_at",
            ]
        )

        return document

    except Exception as exc:
        error = str(exc)
        if client is not None:
            try:
                partial_ids = get_document_point_ids(client, document.pk)
                delete_points(client, partial_ids)
            except Exception as cleanup_exc:
                logger.exception(
                    "Could not clean partial Qdrant index",
                    extra={
                        "document_id": document.pk,
                        "stage": "indexing_cleanup",
                    },
                )
                error = (
                    f"{error}; partial Qdrant cleanup failed: "
                    f"{cleanup_exc}"
                )
        logger.exception(
            "Document indexing failed",
            extra={"document_id": document.pk, "stage": "indexing"},
        )
        Document.objects.filter(pk=document.pk).update(
            status=DocumentStatus.FAILED,
            processing_started_at=None,
            indexing_status=IndexingStatus.FAILED,
            indexed_chunk_count=0,
            indexing_error=error[:4000],
        )
        raise

    finally:
        if client is not None:
            client.close()