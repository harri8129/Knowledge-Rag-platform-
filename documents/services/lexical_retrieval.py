from django.contrib.postgres.search import (
     SearchQuery,
     SearchRank,
     SearchVector
)

from documents.models import DocumentChunk


def search_lexical_chunks(
    query:str,
    top_k: int = 20,
    document_id: int | None = None,
) -> list[dict]:
   
    query = query.strip()

    if not query:
       raise ValueError("Search query cannot be empty")

    if top_k < 1:
       raise ValueError("top_k must be greater than zero")

    search_vector = (
       SearchVector(
          "content",
          weight="A",
       )
    )

    search_query = SearchQuery(
       query,
       search_type="websearch"
    )

    queryset = (
       DocumentChunk.objects
       .annotate(
          search_rank = SearchRank(
             search_vector,
             search_query,
          )
       )
    .filter(search_rank__gt=0)
    .select_related("document")
    .order_by("-search_rank")
    )

    if document_id is not None:
        queryset = queryset.filter(
           document_id = document_id
       )

    chunks = queryset[:top_k]

    results = []

    for chunk in chunks:
       results.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_title": (
                    chunk.document.title
                ),
                "page_number": (
                    chunk.source_page.page_number
                ),
                "chunk_index": (
                    chunk.chunk_index
                ),
                "content": chunk.content,
                "lexical_score": float(
                    chunk.search_rank
                ),
          }
       )

    return results 