import math


def calculate_recall_at_K(
    expected_chunk_ids: list[int],
    retrieved_chunk_ids: list[int],
) -> float:
    if not expected_chunk_ids:
        return 0.0

    expected = set(expected_chunk_ids)
    retrieved = set(retrieved_chunk_ids)
    found = expected.intersection(retrieved)

    return len(found) / len(expected)


def calculate_precision_at_k(
    expected_chunk_ids: list[int],
    retrieved_chunk_ids: list[int],
    k: int | None = None,
) -> float:

    if not retrieved_chunk_ids:
        return 0.0

    if k is not None and k < 1:
        raise ValueError("K must be greater than zero")

    limit = k if k is not None else len(retrieved_chunk_ids)

    expected = set(expected_chunk_ids)
    retrieved_at_k = retrieved_chunk_ids[:limit]
    relevant_found = len(set(retrieved_at_k) & expected)

    return relevant_found / limit


def calculate_reciprocal_rank(
    expected_chunk_ids: list[int],
    retrieved_chunk_ids: list[int],
) -> float:

    expected = set(
        expected_chunk_ids
    )

    for position, chunk_id in enumerate(
        retrieved_chunk_ids,
        start=1,
    ):
        if chunk_id in expected:
            return 1.0 / position

    return 0.0


def calculate_hit_rate_at_k(
    expected_chunk_ids: list[int],
    retrieved_chunk_ids: list[int],
    k: int,
) -> float:

    if k < 1:
        raise ValueError("K must be greater than zero")

    expected =  set(expected_chunk_ids)
    return float(bool(expected.intersection(retrieved_chunk_ids[:k])))


def calculate_ndcg_at_k(
    expected_chunk_ids: list[int],
    retrieved_chunk_ids: list[int],
    k: int,
) -> float:

    if k < 1:
        raise ValueError("K must be greater than zero")

    if not expected_chunk_ids:
        return 0.0

    expected = set(expected_chunk_ids)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, chunk_id in enumerate(retrieved_chunk_ids[:k], start=1)
        if chunk_id in expected
    )

    ideal_relevant_count = min(len(expected), k)
    idcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_relevant_count + 1)
    )

    return dcg / idcg if idcg else 0.0