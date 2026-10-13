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
) -> float:

    if not retrieved_chunk_ids:
        return 0.0

    expected = set(
        expected_chunk_ids
    )

    retrieved = set(
        retrieved_chunk_ids
    )

    found = expected.intersection(
        retrieved
    )

    return len(found) / len(retrieved)