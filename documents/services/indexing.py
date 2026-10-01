from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import transaction 

from documents.models import (
    Document,
    DocumentChunk,
    ChunkingStatus,
    IndexingStatus,
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


def stable_point_id(chunk_id:int) -> str:
    """ 
    Produce a deterministic UUID so retries update the same 
    Qdrant point instead of creating duplicates.
    """
    return str(uuid5(NAMESPACE_URL,
            f"rag-knowledge-engine:chunk:{chunk_id}",                    )
    )

def process_document_indexing(document_id:int):
    document = Document.objects.get(id=document_id)

    if document.chunking_status != ChunkingStatus.READY:
        raise ValueError("Document must be chunked before indexing")

    if document.indexing_status == IndexingStatus.PROCESSING:
        raise ValueError("Document is already being indexed")

    with transaction.atomic():
        document.indexing_status = IndexingStatus.PROCESSING
        document.indexing_error = ""
        document.save(
            update_fields=["indexing_status","indexing_error","updated_at"]
        )        

    client = get_qdrant_client()

    try:
        ensure_collection(client)

        old_point_ids = set(
            get_document_point_ids(client, document.id)
        )
        current_point_ids = set()

        chunks = (
            DocumentChunk.objects
            .filter(document=document)
            .select_related("source_page", "document")
            .order_by("chunk_index")
        )

        batch_size = settings.EMBEDDING_BATCH_SIZE
        indexed_count = 0

        chunk_iterator = iter(chunks.iterator(chunk_size=batch_size))

        while True:
            batch = []
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
                            "document_id": document.id,
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

            Document.objects.filter(id=document.id).update(
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
        document.save(
            update_fields=[
                "indexed_chunk_count",
                "indexing_status",
                "indexing_error",
                "updated_at",
            ]
        )

        return document

    except Exception as exc:
        Document.objects.filter(id=document.id).update(
            indexing_status=IndexingStatus.FAILED,
            indexing_error=str(exc),
        )
        raise

    finally:
        client.close()