import json
from time import perf_counter
from pathlib import Path
from typing import Any

from django.conf import settings

from documents.services.evaluation import (
    calculate_precision_at_k,
    calculate_recall_at_K,
    calculate_reciprocal_rank,
)
from documents.services.hybrid_retrieval import (
    search_hybrid_chunks,
)
from documents.services.retrieval import (
    search_similar_chunks,
)
from documents.services.context import build_context_documents
from documents.services.context_optimizer import (
    optimize_context,
    sort_context_results,
)
from documents.services.citations import extract_citation_ids
from documents.services.llm import generate_answer_with_usage
from documents.services.prompts import SYSTEM_PROMPT, build_user_prompt
from documents.services.neighbor_retrieval import expand_with_neighbors
from documents.services.query_understanding import analyze_query_with_usage
from documents.services.reranker import rerank_results
from documents.services.hybrid_retrieval import search_hybrid_multi_query


def _load_questions(dataset_path: str | Path) -> list[dict[str, Any]]:
    path = Path(dataset_path)

    try:
        with path.open(encoding="utf-8") as dataset_file:
            questions = json.load(dataset_file)
    except OSError as exc:
        raise ValueError(
            f"Could not read evaluation dataset '{path}': {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Evaluation dataset '{path}' is not valid JSON: {exc}"
        ) from exc

    if not isinstance(questions, list) or not questions:
        raise ValueError(
            "Evaluation dataset must be a non-empty JSON array."
        )

    for index, item in enumerate(questions):
        if not isinstance(item, dict):
            raise ValueError(
                f"Evaluation question at index {index} must be an object."
            )

        question = item.get("question")
        expected_ids = item.get("expected_chunk_ids")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(
                f"Evaluation question at index {index} needs a non-empty question."
            )
        if (
            not isinstance(expected_ids, list)
            or not expected_ids
            or any(
                not isinstance(chunk_id, int) or isinstance(chunk_id, bool)
                or chunk_id < 1
                for chunk_id in expected_ids
            )
        ):
            raise ValueError(
                f"Evaluation question at index {index} needs a non-empty "
                "expected_chunk_ids list of integers."
            )

    return questions


def _chunk_ids(results: list[dict]) -> list[int]:
    return [
        chunk_id
        for result in results
        if isinstance(
            (chunk_id := result.get("chunk_id")),
            int,
        )
        and not isinstance(chunk_id, bool)
    ]


def _calculate_metrics(
    expected_ids: list[int],
    retrieved_ids: list[int],
) -> dict[str, float]:
    return {
        "recall_at_k": calculate_recall_at_K(
            expected_chunk_ids=expected_ids,
            retrieved_chunk_ids=retrieved_ids,
        ),
        "precision_at_k": calculate_precision_at_k(
            expected_chunk_ids=expected_ids,
            retrieved_chunk_ids=retrieved_ids,
        ),
        "mrr": calculate_reciprocal_rank(
            expected_chunk_ids=expected_ids,
            retrieved_chunk_ids=retrieved_ids,
        ),
    }


def evaluate_retrieval_dataset(
    dataset_path: str | Path | None = None,
    top_k: int = 5,
    score_threshold: float | None = None,
    document_id: int | None = None,
) -> dict[str, Any]:
    if top_k < 1 or top_k > 50:
        raise ValueError("top_k must be between 1 and 50.")

    if score_threshold is None:
        score_threshold = settings.RAG_MIN_SCORE
    if not 0.0 <= score_threshold <= 1.0:
        raise ValueError(
            "score_threshold must be between 0.0 and 1.0."
        )

    if dataset_path is None:
        dataset_path = (
            settings.BASE_DIR
            / "documents"
            / "evaluation"
            / "questions.json"
        )

    questions = _load_questions(dataset_path)
    per_question = []
    strategy_totals = {
        "dense": {
            "recall_at_k": 0.0,
            "precision_at_k": 0.0,
            "mrr": 0.0,
        },
        "hybrid": {
            "recall_at_k": 0.0,
            "precision_at_k": 0.0,
            "mrr": 0.0,
        },
    }

    for item in questions:
        query = item["question"].strip()
        expected_ids = item["expected_chunk_ids"]
        dense_results = search_similar_chunks(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            document_id=document_id,
        )
        hybrid_results = search_hybrid_chunks(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            document_id=document_id,
            dense_results=dense_results,
        )

        dense_ids = _chunk_ids(dense_results)
        hybrid_ids = _chunk_ids(hybrid_results)
        dense_metrics = _calculate_metrics(
            expected_ids,
            dense_ids,
        )
        hybrid_metrics = _calculate_metrics(
            expected_ids,
            hybrid_ids,
        )

        for metric in strategy_totals["dense"]:
            strategy_totals["dense"][metric] += dense_metrics[metric]
            strategy_totals["hybrid"][metric] += hybrid_metrics[metric]

        per_question.append(
            {
                "question": query,
                "expected_chunk_ids": expected_ids,
                "dense": {
                    "retrieved_chunk_ids": dense_ids,
                    **dense_metrics,
                },
                "hybrid": {
                    "retrieved_chunk_ids": hybrid_ids,
                    **hybrid_metrics,
                },
            }
        )

    question_count = len(questions)
    averages = {
        strategy: {
            metric: score / question_count
            for metric, score in totals.items()
        }
        for strategy, totals in strategy_totals.items()
    }

    return {
        "dataset": str(dataset_path),
        "question_count": question_count,
        "top_k": top_k,
        "score_threshold": score_threshold,
        "averages": averages,
        "questions": per_question,
    }


PHASE_10_STRATEGIES = ("A", "B", "C", "D", "E")
ANSWER_JUDGE_SYSTEM_PROMPT = """
You are an impartial answer-quality evaluator.
Compare each candidate answer with the reference answer. Score semantic
correctness and completeness from 0.0 to 1.0. Penalize factual errors and
unsupported claims. Return only JSON mapping each supplied strategy label to
an object with numeric "score" and a brief "rationale".
""".strip()


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _token_totals(
    usages: list[dict[str, int | None]],
) -> dict[str, int | None]:
    totals: dict[str, int | None] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        values = [usage[key] for usage in usages]
        if values and all(value is not None for value in values):
            totals[key] = sum(value for value in values if value is not None)
        else:
            totals[key] = None
    return totals


def _phase_10_metrics(
    expected_ids: list[int],
    retrieved_ids: list[int],
) -> dict[str, float]:
    retrieved_at_k = retrieved_ids[:5]
    return {
        "recall_at_5": calculate_recall_at_K(
            expected_chunk_ids=expected_ids,
            retrieved_chunk_ids=retrieved_at_k,
        ),
        "precision_at_5": calculate_precision_at_k(
            expected_chunk_ids=expected_ids,
            retrieved_chunk_ids=retrieved_at_k,
        ),
        "mrr": calculate_reciprocal_rank(
            expected_chunk_ids=expected_ids,
            retrieved_chunk_ids=retrieved_at_k,
        ),
    }


def _judge_answers(
    reference_answer: str,
    answers: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, int | None]]:
    prompt = json.dumps(
        {
            "reference_answer": reference_answer,
            "candidate_answers": answers,
        },
        ensure_ascii=False,
    )
    response, usage = generate_answer_with_usage(
        system_prompt=ANSWER_JUDGE_SYSTEM_PROMPT,
        user_prompt=prompt,
    )
    try:
        scores = json.loads(response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Answer judge returned invalid JSON: {exc}"
        ) from exc
    if not isinstance(scores, dict):
        raise RuntimeError("Answer judge response must be a JSON object.")

    validated: dict[str, dict[str, Any]] = {}
    for strategy in PHASE_10_STRATEGIES:
        result = scores.get(strategy)
        if not isinstance(result, dict):
            raise RuntimeError(
                f"Answer judge omitted strategy {strategy}."
            )
        score = result.get("score")
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not 0.0 <= score <= 1.0
        ):
            raise RuntimeError(
                f"Answer judge returned an invalid score for strategy {strategy}."
            )
        validated[strategy] = {
            "score": float(score),
            "rationale": str(result.get("rationale", "")),
        }
    return validated, usage


def evaluate_phase_10_dataset(
    dataset_path: str | Path | None = None,
    top_k: int = 5,
    score_threshold: float | None = None,
    document_id: int | None = None,
    evaluate_answers: bool = False,
    include_rewriting: bool = True,
) -> dict[str, Any]:
    if top_k < 5 or top_k > 50:
        raise ValueError("top_k must be between 5 and 50 for Recall@5.")
    if score_threshold is None:
        score_threshold = settings.RAG_MIN_SCORE
    if not 0.0 <= score_threshold <= 1.0:
        raise ValueError("score_threshold must be between 0.0 and 1.0.")
    if evaluate_answers and not include_rewriting:
        raise ValueError(
            "Answer evaluation requires all five strategies, including rewriting."
        )
    if dataset_path is None:
        dataset_path = (
            settings.BASE_DIR
            / "documents"
            / "evaluation"
            / "questions.json"
        )

    questions = _load_questions(dataset_path)
    if evaluate_answers:
        for index, item in enumerate(questions):
            if not isinstance(item.get("reference_answer"), str) or not item[
                "reference_answer"
            ].strip():
                raise ValueError(
                    f"Evaluation question at index {index} needs a "
                    "reference_answer when answer evaluation is enabled."
                )
            expected_citations = item.get("expected_citations")
            if (
                not isinstance(expected_citations, list)
                or not expected_citations
                or any(
                    not isinstance(chunk_id, int)
                    or isinstance(chunk_id, bool)
                    or chunk_id < 1
                    for chunk_id in expected_citations
                )
            ):
                raise ValueError(
                    f"Evaluation question at index {index} needs a non-empty "
                    "expected_citations list of chunk IDs."
                )

    stage_totals: dict[str, dict[str, list[float]]] = {
        strategy: {
            name: []
            for name in (
                "recall_at_5",
                "precision_at_5",
                "mrr",
                "retrieval_latency_ms",
                "answer_latency_ms",
                "answer_score",
                "citation_precision",
                "citation_recall",
                "citation_exact",
            )
        }
        for strategy in PHASE_10_STRATEGIES
    }
    stage_usages: dict[str, list[dict[str, int | None]]] = {
        strategy: [] for strategy in PHASE_10_STRATEGIES
    }
    judge_usages: list[dict[str, int | None]] = []
    per_question: list[dict[str, Any]] = []

    for item in questions:
        query = item["question"].strip()
        expected_ids = item["expected_chunk_ids"]
        question_document_id = (
            document_id
            if document_id is not None
            else item.get("document_id")
        )
        retrieval_started = perf_counter()

        dense_all = search_similar_chunks(
            query=query,
            top_k=max(top_k, 20),
            score_threshold=score_threshold,
            document_id=question_document_id,
        )
        dense_latency = (perf_counter() - retrieval_started) * 1000

        hybrid_started = perf_counter()
        hybrid_all = search_hybrid_chunks(
            query=query,
            top_k=max(top_k, 20),
            score_threshold=score_threshold,
            document_id=question_document_id,
            dense_results=dense_all,
        )
        hybrid_latency = (perf_counter() - hybrid_started) * 1000

        rerank_started = perf_counter()
        reranked = rerank_results(
            query=query,
            results=hybrid_all,
            top_k=top_k,
        )
        rerank_latency = (perf_counter() - rerank_started) * 1000

        retrieved_by_strategy = {
            "A": dense_all[:top_k],
            "B": hybrid_all[:top_k],
            "C": reranked,
        }
        retrieval_latencies = {
            "A": dense_latency,
            "B": dense_latency + hybrid_latency,
            "C": dense_latency + hybrid_latency + rerank_latency,
        }
        active_strategies = ("A", "B", "C")
        rewrite_usage: dict[str, int | None] | None = None
        if include_rewriting:
            rewrite_started = perf_counter()
            rewrite_plan, rewrite_usage = analyze_query_with_usage(query)
            rewrite_latency = (perf_counter() - rewrite_started) * 1000
            rewritten_queries = [
                query,
                rewrite_plan.rewritten_query,
                *rewrite_plan.expanded_queries,
            ]
            rewritten_queries = list(dict.fromkeys(
                value.strip()
                for value in rewritten_queries
                if value and value.strip()
            ))[:3]
            rewritten_started = perf_counter()
            rewritten_hybrid = search_hybrid_multi_query(
                queries=rewritten_queries,
                top_k=max(top_k, 20),
                score_threshold=score_threshold,
                document_id=question_document_id,
            )
            rewritten_reranked = rerank_results(
                query=query,
                results=rewritten_hybrid,
                top_k=top_k,
            )
            rewritten_latency = (
                perf_counter() - rewritten_started
            ) * 1000

            neighbor_started = perf_counter()
            expanded = expand_with_neighbors(
                rewritten_reranked,
                window=1,
            )
            expanded = sort_context_results(expanded)
            expanded = optimize_context(
                expanded,
                max_chunks=max(top_k + 1, settings.RAG_MAX_CONTEXT_CHUNKS),
            )
            neighbor_latency = (perf_counter() - neighbor_started) * 1000
            retrieved_by_strategy.update(
                {
                    "D": rewritten_reranked,
                    "E": expanded,
                }
            )
            retrieval_latencies.update(
                {
                    "D": rewrite_latency + rewritten_latency,
                    "E": (
                        rewrite_latency
                        + rewritten_latency
                        + neighbor_latency
                    ),
                }
            )
            active_strategies = PHASE_10_STRATEGIES

        question_result: dict[str, Any] = {
            "id": item.get("id"),
            "question": query,
            "document_id": question_document_id,
            "expected_chunk_ids": expected_ids,
            "strategies": {},
        }
        answers: dict[str, str] = {}
        source_records: dict[str, list[dict]] = {}

        for strategy in active_strategies:
            results = retrieved_by_strategy[strategy]
            retrieved_ids = _chunk_ids(results)
            metrics = _phase_10_metrics(expected_ids, retrieved_ids)
            stage = {
                "retrieved_chunk_ids": retrieved_ids,
                **metrics,
                "retrieval_latency_ms": retrieval_latencies[strategy],
            }
            for metric, value in metrics.items():
                stage_totals[strategy][metric].append(value)
            stage_totals[strategy]["retrieval_latency_ms"].append(
                retrieval_latencies[strategy]
            )

            if evaluate_answers:
                sources = build_context_documents(results)
                source_records[strategy] = sources
                prompt = build_user_prompt(query=query, sources=sources)
                answer_started = perf_counter()
                answer, usage = generate_answer_with_usage(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt,
                )
                answer_latency = (perf_counter() - answer_started) * 1000
                answers[strategy] = answer
                stage["answer"] = answer
                stage["answer_latency_ms"] = answer_latency
                stage_totals[strategy]["answer_latency_ms"].append(
                    answer_latency
                )
                stage_usages[strategy].append(usage)
            question_result["strategies"][strategy] = stage

        if evaluate_answers:
            judged, judge_usage = _judge_answers(
                reference_answer=item["reference_answer"],
                answers=answers,
            )
            judge_usages.append(judge_usage)
            question_result["reference_answer"] = item["reference_answer"]
            expected_citations = set(item["expected_citations"])

            for strategy in PHASE_10_STRATEGIES:
                stage = question_result["strategies"][strategy]
                sources = source_records[strategy]
                source_id_to_chunk_id = {
                    source["source_id"]: source.get("chunk_id")
                    for source in sources
                }
                cited_source_ids = extract_citation_ids(stage["answer"])
                cited_chunk_ids = {
                    source_id_to_chunk_id[source_id]
                    for source_id in cited_source_ids
                    if source_id in source_id_to_chunk_id
                    and isinstance(source_id_to_chunk_id[source_id], int)
                }
                correct_citations = cited_chunk_ids & expected_citations
                citation_precision = (
                    len(correct_citations) / len(cited_chunk_ids)
                    if cited_chunk_ids
                    else 0.0
                )
                citation_recall = (
                    len(correct_citations) / len(expected_citations)
                    if expected_citations
                    else 0.0
                )
                citation_exact = float(
                    cited_chunk_ids == expected_citations
                )
                answer_score = judged[strategy]["score"]
                stage["answer_score"] = answer_score
                stage["answer_correct"] = answer_score >= 0.7
                stage["answer_judge_rationale"] = judged[strategy]["rationale"]
                stage["cited_chunk_ids"] = sorted(cited_chunk_ids)
                stage["citation_precision"] = citation_precision
                stage["citation_recall"] = citation_recall
                stage["citation_exact"] = bool(citation_exact)
                stage["citation_correct"] = bool(citation_exact)
                stage_totals[strategy]["answer_score"].append(answer_score)
                stage_totals[strategy]["citation_precision"].append(
                    citation_precision
                )
                stage_totals[strategy]["citation_recall"].append(
                    citation_recall
                )
                stage_totals[strategy]["citation_exact"].append(citation_exact)
                if strategy in ("D", "E") and rewrite_usage is not None:
                    stage_usages[strategy].append(rewrite_usage)

        per_question.append(question_result)

    summaries: dict[str, dict[str, Any]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for strategy in PHASE_10_STRATEGIES:
        if strategy not in active_strategies:
            summaries[strategy] = {"status": "not_run"}
            continue
        totals = stage_totals[strategy]
        summary = {
            "recall_at_5": _average(totals["recall_at_5"]),
            "precision_at_5": _average(totals["precision_at_5"]),
            "mrr": _average(totals["mrr"]),
            "retrieval_latency_ms": _average(
                totals["retrieval_latency_ms"]
            ),
        }
        if evaluate_answers:
            summary.update(
                {
                    "answer_score": _average(totals["answer_score"]),
                    "answer_correctness_rate": _average(
                        [float(score >= 0.7) for score in totals["answer_score"]]
                    ),
                    "citation_precision": _average(
                        totals["citation_precision"]
                    ),
                    "citation_recall": _average(
                        totals["citation_recall"]
                    ),
                    "citation_exact_rate": _average(
                        totals["citation_exact"]
                    ),
                    "answer_latency_ms": _average(
                        totals["answer_latency_ms"]
                    ),
                    "answer_and_rewrite_tokens": _token_totals(
                        stage_usages[strategy]
                    ),
                }
            )
        summaries[strategy] = summary

    return {
        "dataset": str(dataset_path),
        "question_count": len(questions),
        "top_k": top_k,
        "score_threshold": score_threshold,
        "strategies_run": list(active_strategies),
        "answer_evaluation": evaluate_answers,
        "averages": summaries,
        "answer_judge_tokens": _token_totals(judge_usages),
        "questions": per_question,
    }
