from functools import lru_cache

from django.conf import settings
from sentence_transformers import CrossEncoder

@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:

    model_name = getattr(
        settings,
        "RERANKER_MODEL",
        None
    )

    if not model_name:
        raise RuntimeError(
            "RERANKER_MODEL is not configured."
        )

    return CrossEncoder(model_name)


def rerank_results(query:str, results:list[dict],top_k: int = 6,) -> list[dict]:
    """ 
    ReRank retrieved chunks using a cross-encoder .

    The cross-encoder recieves 

        (query,chunk)

    and produces a relevance score
    """

    query = query.strip()

    if not query:
        raise ValueError("Query cannot be empty")

    if not results:
        return []

    if top_k < 1:
        raise ValueError("top_k must be greater than zero ")

    pairs = []

    for result in results:
        content = result.get("content","")

        if not content.strip():
            continue

        pairs.append((query,content))

    if not pairs:
        return []

    reranker = get_reranker()

    scores = reranker.predict(pairs)

    scored_results = []

    result_index = 0 

    for result in results:
        content = result.get("content","")

        if not content.strip():
            continue

        result_copy = result.copy()

        result_copy["rerank_score"] = float(scores[result_index])

        scored_results.append(result_copy)

        result_index += 1 

    scored_results.sort(
        key = lambda item: item["rerank_score"],
        reverse=True
    )

    return scored_results[:top_k]