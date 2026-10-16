from django.conf import settings

from documents.services.citations import validation_citations
from documents.services.context import build_context_documents
from documents.services.context_optimizer import optimize_context, sort_context_results
from documents.services.llm import generate_answer
from documents.services.neighbor_retrieval import expand_with_neighbors
from documents.services.prompts import SYSTEM_PROMPT,build_user_prompt
from documents.services.hybrid_retrieval import search_hybrid_multi_query
from documents.services.query_understanding import analyze_query
from documents.services.retrieval_quality import limit_results,prepare_retrieval_results
from documents.services.reranker import rerank_results


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
    # 1. Query Understanding
    # ----------------------------------------
    if settings.ENABLE_QUERY_REWRITING:

        try:
            query_plan = analyze_query(
                query
            )
        except Exception:
            query_plan = None

    else:

        query_plan = None

    if query_plan:

        search_queries = [
            query_plan.original_query,
            query_plan.rewritten_query,
            *query_plan.expanded_queries,
        ]
    else:
        search_queries = [query]

    #Remove duplicates 
    search_queries = list(
        dict.fromkeys(
            q.strip()
            for q in search_queries
            if q.strip()
        )
    )

    search_queries = search_queries[:3]

    # ----------,------------------------------
    # 2. Hybrid multi-query retrieval
    # ----------------------------------------

    retrieved_results = (
        search_hybrid_multi_query(
            queries=search_queries,
            top_k=top_k,
            score_threshold=score_threshold,
            document_id=document_id,
        )
    )

    # ----------------------------------------
    # 3. Retrieval quality Processing
    # ----------------------------------------

    candidate_results = (
        prepare_retrieval_results(
            retrieved_results,
            max_results=None,
        )
    )

    if not candidate_results:

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
                "search_queries": search_queries,
                "retrieved_count": len(retrieved_results),
                "candidate_count": 0,
                "reranked_count": 0,
                "context_count": 0,
            },
        }

    # ----------------------------------------
    # 4. Reranking
    # ----------------------------------------

    reranked_results = rerank_results(
        query=query,
        results=candidate_results,
        top_k=settings.RERANKER_TOP_K,
    )

    if not reranked_results:

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
                "search_queries": search_queries,
                "retrieved_count": len(retrieved_results),
                "candidate_count": len(candidate_results),
                "reranked_count": 0,
                "context_count": 0,
            },
        }

    # ----------------------------------------
    # 5. neighbor expansion 
    # ----------------------------------------
    expanded_results = (
        expand_with_neighbors(
            reranked_results,
            window = 1,
        )
    )

    # ----------------------------------------
    # 6. Context optimiation
    # ----------------------------------------
    expanded_results = (
        sort_context_results(
            expanded_results
        )
    )

    optimized_results = (
        optimize_context(
            expanded_results,
            max_chunks=(
                settings.RAG_MAX_CONTEXT_CHUNKS
            ),
        )
    )

    # ----------------------------------------
    # 7. Build trusted source records
    # ----------------------------------------

    sources = build_context_documents(
        optimized_results
    )

    # ----------------------------------------
    # 8. Build grounded prompt
    # ----------------------------------------

    user_prompt = build_user_prompt(
        query=query,
        sources=sources,
    )

    # ----------------------------------------
    # 9. Generate answer
    # ----------------------------------------

    answer = generate_answer(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # ----------------------------------------
    # 10. Validate citations
    # ----------------------------------------

    citation_info = validation_citations(
        answer=answer,
        sources=sources,
    )

    # ----------------------------------------
    # 11. Public source 
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

                "dense_score": source.get(
                    "dense_score"
                ),

                "lexical_score": source.get(
                    "lexical_score"
                ),

                "rrf_score": source.get(
                    "rrf_score"
                ),

                "dense_rank": source.get(
                    "dense_rank"
                ),

                "lexical_rank": source.get(
                    "lexical_rank"
                ),

                "rerank_score": source.get(
                    "rerank_score"
                ),

                "is_neighbor": source.get(
                    "is_neighbor",
                    False,
                ),
            }
        )

    # ----------------------------------------
    # 12. Final response
    # ----------------------------------------

    return {
        "query": query,
        "answer": answer,
        "sources": public_sources,
        "citations": citation_info,
        "retrieval": {
            "search_queries": search_queries,
            "retrieved_count": len(
                retrieved_results
            ),
            "candidate_count": len(
                candidate_results
            ),
            "reranked_count": len(
                reranked_results
            ),
            "context_count": len(
                sources
            ),
        },
    }