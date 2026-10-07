from qdrant_client.http.models.models import ScrollRequest
from typing_extensions import NoExtraItems
from django.conf import settings
from qdrant_client import QdrantClient, models

from documents.services.embeddings import embed_texts
from documents.services.vector_store import get_qdrant_client

def search_similar_chunks(
    query: str,
    top_k: int = 5,
    score_threshold: float | None = None,
    document_id: int | None = None 
):
    """
    Retrieve semantically similar document chunks from Qdrant.

    Args:
        query: Natural language search query.
        top_k: Maximum number of chunks to return.
        score_threshold: Optional minimum similarity score.
        document_id: Optional document filter.

    Returns:
        A list of matching chunk dictionaries.
    """

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty")

    if top_k < 1 or top_k > 50:
        raise ValueError("top_k must be between 1 and 50")

    if score_threshold is not None:
        if not 0.0 <= score_threshold <= 1.0:
            raise ValueError("Score threshold must be between 0.0 and 1.0")

    # -----------------------------------
    # 1. Convert query into embedding
    # -----------------------------------
    vectors = embed_texts([query])
    query_vector = vectors[0]

    # -----------------------------------
    # 2. Buid document filter  
    # -----------------------------------
    must_conditions = []

    if document_id is not None:
        must_conditions.append(
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(
                    value=document_id
                )

            )
        )

    query_filter = (
        models.Filter(must=must_conditions)
        if must_conditions
        else None
    )

    # -----------------------------------
    # 3. Query Qdrant
    # -----------------------------------
    client = get_qdrant_client()

    try:
        if not client.collection_exists(
            settings.QDRANT_COLLECTION
        ):
            return []

        response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,  
            with_payload=True,
            with_vectors=False,
        )    

        # -----------------------------------
        # 4. Convert qdrant results
        # -----------------------------------
        results = []

        for point in response.points:
            payload = point.payload or {}

            results.append({
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "document_title": payload.get("document_title"),
                "page_number": payload.get("page_number"),
                "chunk_index": payload.get("chunk_index"),
                "content": payload.get("content", ""),
                "score": float(point.score),
            })

        return results

    finally:
        client.close()