def optimize_context(results: list[dict],max_chunks: int = 6,) -> list[dict]:

    if max_chunks < 1:
        raise ValueError("max_chunks must be greater thean zero")

    if not results:
        return []

    primary = []
    neighbors = []

    for result in results:

        if result.get("is_neighbor",False):
            neighbors.append(result)
        else:
            primary.append(result)

    selected = []

    #Primary chunks first 
    for result in primary:

        if len(selected) >= max_chunks:
            break

        selected.append(result)

    #Then supporting neighbors
    for result in neighbors:

        if len(selected) >= max_chunks:
            break

        selected.append(result)

    return selected


def sort_context_results(results: list[dict],) -> list[dict]:

    return sorted(
        results,
        key=lambda result : (
            result.get("is_neighbor",False),
            -result.get("rerank_score",
                        result.get("rrf_score",0.0)),

            result.get("chunk_index",0),
        )
    )