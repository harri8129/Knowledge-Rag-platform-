from documents.models import DocumentChunk


def get_neighbor_chunks(chunk_id:int, window: int = 1) -> list[dict]:

    if window < 1:
        return []

    try:
        chunk = (
            DocumentChunk.objects
            .select_related("document")
            .get(id=chunk_id)
        )

    except DocumentChunk.DoesNotExist:
        return []

    minimum_index = max(0,chunk.chunk_index - window,)

    maximum_index = (chunk.chunk_index + window)

    chunks = (
        DocumentChunk.objects
        .select_related("document")
        .filter(
            document_id=chunk.document_id,
            chunk_index__gte=minimum_index,
            chunk_index__lte=maximum_index,
        )
        .order_by("chunk_index")
    )

    results = []

    for item in chunks:

        results.append(
            {
                "chunk_id": item.id,
                "document_id": item.document_id,
                "document_title": (
                    item.document.title
                ),
                "page_number": (
                    item.source_page.page_number
                ),
                "chunk_index": (
                    item.chunk_index
                ),
                "content": item.content,
                "is_neighbor": (
                    item.id != chunk.id
                ),
            }
        )

    return results


def expand_with_neighbors(
    results: list[dict],
    window: int = 1,
) -> list[dict] :

    if not results:
        return []

    expanded = {}

    for result in results:

        chunk_id = result.get("chunk_id")

        if chunk_id is None:
            continue

        expanded[chunk_id] = dict(result)

        neighbors = get_neighbor_chunks(
            chunk_id=chunk_id,
            window=window
        )

        for neighbor in neighbors:

            neighbor_id = neighbor["chunk_id"]

            if neighbor_id in expanded:
                continue

            expanded[neighbor_id] = neighbor

    return list(expanded.values())