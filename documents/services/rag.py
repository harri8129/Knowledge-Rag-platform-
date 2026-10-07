from django.conf import settings

from documents.services.llm import generate_answer
from documents.services.retrieval import search_similar_chunks
from documents.services.prompts import (
    SYSTEM_PROMPT,build_user_prompt
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
            "Question cannot be empty"
        )
    
    if top_k is None:
        top_k = settings.RAG_TOP_K

    if score_threshold is None:
        score_threshold = settings.RAG_SCORE_THRESHOLD
    
    # -----------------------------------------
    # 1. Retrieve relevant chunks
    # -----------------------------------------

    results = search_similar_chunks(
        query=query,
        top_k=top_k,
        score_threshold=score_threshold,
        document_id=document_id,
    )
  
    # -----------------------------------------
    # 2. No Context
    # -----------------------------------------
    if not results:
        return {
            "query": query,
            "answer": (
                "I could not find enough relevant information "
                "in the provided documents to answer this question."
            ),
            "sources": [],
        }
        
    # -----------------------------------------
    # 3. Build prompt
    # -----------------------------------------

    user_prompt = build_user_prompt(
        query=query,
        results=results,
    )

    # -----------------------------------------
    # 4. Generate answer
    # -----------------------------------------

    answer = generate_answer(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # -----------------------------------------
    # 5. Prepare sources
    # -----------------------------------------

    sources = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        sources.append(
            {
                "source_id": f"S{index}",
                "chunk_id": result.get("chunk_id"),
                "document_id": result.get("document_id"),
                "document_title": result.get(
                    "document_title"
                ),
                "page_number": result.get(
                    "page_number"
                ),
                "score": result.get("score"),
            }
        )

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
    }