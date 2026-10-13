from collections import OrderedDict


def filter_by_score(
    results: list[dict],
    minimum_score: float | None = None,
) -> list[dict]:

    if minimum_score is None:
        return results

    return [
        result
        for result in results
        if result.get(
            "score",
            0.0,
        ) >= minimum_score
    ]


def deduplicate_results(
    results: list[dict],
) -> list[dict]:

    unique = OrderedDict()

    for result in results:

        chunk_id = result.get(
            "chunk_id"
        )

        if chunk_id is not None:
            key = f"chunk:{chunk_id}"
        else:
            key = (
                f"{result.get('document_id')}:"
                f"{result.get('page_number')}:"
                f"{result.get('content', '')}"
            )

        if key not in unique:
            unique[key] = result

    return list(
        unique.values()
    )


def limit_results(
    results: list[dict],
    limit: int,
) -> list[dict]:
    if limit < 1:
        raise ValueError(
            "Limit must be greater than zero"
        )

    return results[:limit]


def prepare_retrieval_results(
    results: list[dict],
    minimum_score: float | None = None,
    max_results: int | None = None,
) -> list[dict]:

    results = filter_by_score(
        results,
        minimum_score,
    )

    results = deduplicate_results(
        results
    )

    if max_results is not None:
        results = limit_results(
            results,
            max_results,
        )

    return results