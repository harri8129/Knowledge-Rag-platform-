def build_context_documents(
    results: list[dict],
) -> list[dict]:

    sources = []

    for index, result in enumerate(
        results,
        start=1,
    ):

        source_id = f"S{index}"

        sources.append(
            {
                "source_id": source_id,

                "chunk_id": result.get(
                    "chunk_id"
                ),

                "document_id": result.get(
                    "document_id"
                ),

                "document_title": result.get(
                    "document_title"
                ),

                "page_number": result.get(
                    "page_number"
                ),

                "chunk_index": result.get(
                    "chunk_index"
                ),

                "content": result.get(
                    "content",
                    "",
                ),

                "dense_score": result.get(
                    "score"
                ),

                "lexical_score": result.get(
                    "lexical_score"
                ),

                "rrf_score": result.get(
                    "rrf_score"
                ),

                "dense_rank": result.get(
                    "dense_rank"
                ),

                "lexical_rank": result.get(
                    "lexical_rank"
                ),

                "rerank_score": result.get(
                    "rerank_score"
                ),

                "is_neighbor": result.get(
                    "is_neighbor",
                    False,
                ),
            }
        )

    return sources

def build_llm_context(
    sources: list[dict],
) -> str:

    if not sources:
        return (
            "No relevant context was found."
        )

    blocks = []

    for source in sources:

        source_id = source[
            "source_id"
        ]

        title = (
            source.get(
                "document_title"
            )
            or "Unknown document"
        )

        page = source.get(
            "page_number"
        )

        content = source.get(
            "content",
            "",
        )

        metadata = (
            f"[{source_id}] "
            f"Document: {title}"
        )

        if page is not None:
            metadata += (
                f" | Page: {page}"
            )

        blocks.append(
            f"{metadata}\n"
            f"{content}"
        )

    return "\n\n---\n\n".join(
        blocks
    )
