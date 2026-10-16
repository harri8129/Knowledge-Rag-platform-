from documents.services.lexical_retrieval import search_lexical_chunks
from documents.services.retrieval import search_similar_chunks


def reciprocal_rank_fusion(
    dense_results: list[dict],
    lexical_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """ 
    Combine multiple ranked result lists 
    usign Reciprocal Rank Fusion
    """

    fused = {}

    # ----------------------------------------
    # Dense results
    # ----------------------------------------

    for rank, result in enumerate(
        dense_results,
        start=1,
    ):

        chunk_id = result.get(
            "chunk_id"
        )

        if chunk_id is None:
            continue

        entry = fused.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "rrf_score": 0.0,
                "result": result,
                "dense_rank": None,
                "lexical_rank": None,
            },
        )

        entry["dense_rank"] = rank

        entry["rrf_score"] += (
            1.0 / (k + rank)
        )

    # ----------------------------------------
    # Lexical results
    # ----------------------------------------

    for rank, result in enumerate(
        lexical_results,
        start=1,
    ):

        chunk_id = result.get(
            "chunk_id"
        )

        if chunk_id is None:
            continue

        entry = fused.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "rrf_score": 0.0,
                "result": result,
                "dense_rank": None,
                "lexical_rank": None,
            },
        )

        entry["lexical_rank"] = rank

        entry["rrf_score"] += (
            1.0 / (k + rank)
        )

        # Prefer the dense result because
        # it contains the full retrieval payload.
        entry["result"] = {
            **entry["result"],
            **result,
        }

    # ----------------------------------------
    # Sort
    # ----------------------------------------

    return sorted(
        fused.values(),
        key=lambda item: item[
            "rrf_score"
        ],
        reverse=True,
    )


def search_hybrid_chunks(
    query: str,
    top_k: int = 20,
    score_threshold: float | None = None,
    document_id: int | None = None,
    dense_results: list[dict] | None = None,
) -> list[dict]:

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty")

    # ----------------------------------------
    # Dense retrieval
    # ----------------------------------------

    if dense_results is None:
        dense_results = search_similar_chunks(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            document_id=document_id,
        )

    # ----------------------------------------
    # Lexical retrieval
    # ----------------------------------------

    lexical_results = (
        search_lexical_chunks(
            query=query,
            top_k=top_k,
            document_id=document_id,
        )
    )

    # ----------------------------------------
    # RRF
    # ----------------------------------------

    fused_results = (
        reciprocal_rank_fusion(
            dense_results=dense_results,
            lexical_results=lexical_results,
        )
    )

    # ----------------------------------------
    # Convert result format
    # ----------------------------------------

    results = []

    for item in fused_results:

        result = dict(
            item["result"]
        )

        result["rrf_score"] = item[
            "rrf_score"
        ]

        result["dense_rank"] = item[
            "dense_rank"
        ]

        result["lexical_rank"] = item[
            "lexical_rank"
        ]

        results.append(
            result
        )

    return results[:top_k]


def search_hybrid_multi_query(
    queries: list[str],
    top_k: int = 20,
    score_threshold: float | None = None, 
    document_id: int | None = None,
) -> list[dict]:

    if not queries:
        return []

    unique_queries = []

    for query in queries:

        query = query.strip()

        if not query:
            continue

        if query not in unique_queries:
            unique_queries.append(query)

    unique_queries = unique_queries[:3]

    all_results = []

    for query in unique_queries:
        results = search_hybrid_chunks(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            document_id=document_id,
        )

        all_results.extend(results)

    return merge_hybrid_results(all_results)[:top_k]

def merge_hybrid_results(
    results: list[dict],
) -> list[dict]:

    merged = {}

    for result in results:

        chunk_id = result.get("chunk_id")

        if chunk_id is None:
            continue

        if chunk_id not in merged:

            merged[chunk_id] = dict(result)

            continue

        existing = merged[chunk_id]

        existing["rrf_score"] = (
            existing.get("rrf_score", 0.0)
            + result.get("rrf_score", 0.0)
        )

        for score_name in ("score", "dense_score", "lexical_score"):
            incoming_score = result.get(score_name)
            if incoming_score is None:
                continue
            current_score = existing.get(score_name)
            existing[score_name] = (
                max(current_score, incoming_score)
                if current_score is not None
                else incoming_score
            )

    return sorted(
        merged.values(),
        key=lambda item: item.get(
            "rrf_score",
            0.0
        ),
        reverse=True, 
    )