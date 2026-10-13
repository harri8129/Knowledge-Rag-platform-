from django.conf import settings

from documents.services.citations import validation_citations

from documents.services.context import build_context_documents

from documents.services.llm import (
    generate_answer,
)

from documents.services.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)

from documents.services.retrieval import (
    search_similar_chunks,
)

from documents.services.retrieval_quality import (
    prepare_retrieval_results,
)


def answer_question(
    query: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
    document_id: int | None = None,
) -> dict:

    query = query.strip()

    if not query:
        raise ValueError(
            "Question cannot be empty."
        )

    if top_k is None:
        top_k = settings.RAG_TOP_K

    if score_threshold is None:
        score_threshold = (
            settings.RAG_MIN_SCORE
        )

    # ----------------------------------------
    # 1. Retrieve candidate chunks
    # ----------------------------------------

    retrieved_results = (
        search_similar_chunks(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            document_id=document_id,
        )
    )

    # ----------------------------------------
    # 2. Quality filtering
    # ----------------------------------------

    results = prepare_retrieval_results(
        retrieved_results,
        minimum_score=score_threshold,
        max_results=(
            settings.RAG_MAX_CONTEXT_CHUNKS
        ),
    )

    # ----------------------------------------
    # 3. No relevant context
    # ----------------------------------------

    if not results:

        return {
            "query": query,
            "answer": (
                "The provided documents do not "
                "contain enough information to "
                "answer this question."
            ),
            "sources": [],
            "citations": {
                "cited_sources": [],
                "invalid_citations": [],
                "citation_count": 0,
                "has_invalid_citations": False,
            },
            "retrieval": {
                "retrieved_count": len(
                    retrieved_results
                ),
                "context_count": 0,
            },
        }

    # ----------------------------------------
    # 4. Build trusted source records
    # ----------------------------------------

    sources = build_context_documents(
        results
    )

    # ----------------------------------------
    # 5. Build grounded prompt
    # ----------------------------------------

    user_prompt = build_user_prompt(
        query=query,
        sources=sources,
    )

    # ----------------------------------------
    # 6. Generate answer
    # ----------------------------------------

    answer = generate_answer(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # ----------------------------------------
    # 7. Validate citations
    # ----------------------------------------

    citation_info = validation_citations(
        answer=answer,
        sources=sources,
    )

    # ----------------------------------------
    # 8. Return API response
    # ----------------------------------------

    public_sources = []

    for source in sources:
        public_sources.append(
            {
                "source_id": source[
                    "source_id"
                ],
                "chunk_id": source[
                    "chunk_id"
                ],
                "document_id": source[
                    "document_id"
                ],
                "document_title": source[
                    "document_title"
                ],
                "page_number": source[
                    "page_number"
                ],
                "score": source[
                    "score"
                ],
            }
        )

    return {
        "query": query,
        "answer": answer,
        "sources": public_sources,
        "citations": citation_info,
        "retrieval": {
            "retrieved_count": len(
                retrieved_results
            ),
            "context_count": len(
                sources
            ),
        },
    }