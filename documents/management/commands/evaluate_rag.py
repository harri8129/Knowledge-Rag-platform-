import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from documents.services.retrieval_evaluation import evaluate_phase_10_dataset


STRATEGY_NAMES = {
    "A": "Dense",
    "B": "Hybrid",
    "C": "Hybrid + Reranker",
    "D": "Rewrite + Reranker",
    "E": "Phase 10 pipeline",
}


def _format_score(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "n/a"


def _format_percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else "n/a"


def _format_latency(value: float | None) -> str:
    return f"{value:.0f} ms" if value is not None else "n/a"


class Command(BaseCommand):
    help = "Evaluate RAG retrieval and generation against the golden dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default=None,
            help="Path to a JSON evaluation dataset.",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="Number of ranked results to score (minimum 5).",
        )
        parser.add_argument(
            "--score-threshold",
            type=float,
            default=None,
            help="Dense retrieval score threshold (default: RAG_MIN_SCORE).",
        )
        parser.add_argument(
            "--document-id",
            type=int,
            default=None,
            help="Override dataset document IDs and restrict retrieval.",
        )
        parser.add_argument(
            "--retrieval-only",
            action="store_true",
            help=(
                "Skip answer generation, judging, and query rewriting; "
                "only runs Dense, Hybrid, and Hybrid + Reranker."
            ),
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Optional path for the complete JSON report.",
        )

    def handle(self, *args, **options):
        try:
            report = evaluate_phase_10_dataset(
                dataset_path=options["dataset"],
                top_k=options["top_k"],
                score_threshold=options["score_threshold"],
                document_id=options["document_id"],
                evaluate_answers=not options["retrieval_only"],
                include_rewriting=not options["retrieval_only"],
            )
        except (ValueError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc

        if options["output"]:
            output_path = Path(options["output"])
            try:
                output_path.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as exc:
                raise CommandError(
                    f"Could not write evaluation report to "
                    f"'{output_path}': {exc}"
                ) from exc

        self.stdout.write(self.style.SUCCESS("RAG Evaluation"))
        self.stdout.write("-" * 104)
        self.stdout.write(f"Dataset: {report['question_count']} questions")
        self.stdout.write("")
        self.stdout.write(
            f"{'Strategy':<24} {'Recall@5':>9} {'Precision@5':>12} "
            f"{'MRR':>7} {'Hit@5':>8} {'NDCG@5':>8}"
        )
        for code in report["strategies_run"]:
            metrics = report["averages"][code]
            self.stdout.write(
                f"{STRATEGY_NAMES[code]:<24} "
                f"{_format_score(metrics.get('recall_at_5')):>9} "
                f"{_format_score(metrics.get('precision_at_5')):>12} "
                f"{_format_score(metrics.get('mrr')):>7} "
                f"{_format_score(metrics.get('hit_rate_at_5')):>8} "
                f"{_format_score(metrics.get('ndcg_at_5')):>8}"
            )

        self.stdout.write("")
        if report["answer_evaluation"]:
            self.stdout.write("Generation and system averages")
            for code in report["strategies_run"]:
                metrics = report["averages"][code]
                usage = metrics["llm_usage"]
                self.stdout.write(
                    f"{STRATEGY_NAMES[code]:<24} "
                    f"correct={_format_percent(metrics.get('answer_correctness_rate'))} "
                    f"relevance={_format_percent(metrics.get('answer_relevance'))} "
                    f"faithfulness={_format_percent(metrics.get('faithfulness'))} "
                    f"citation accuracy={_format_percent(metrics.get('citation_exact_rate'))}"
                )
                self.stdout.write(
                    f"{'':<24} "
                    f"retrieval={_format_latency(metrics.get('retrieval_latency_ms'))}, "
                    f"query rewrite={_format_latency(metrics.get('query_rewrite_latency_ms'))}, "
                    f"reranker={_format_latency(metrics.get('reranker_latency_ms'))}, "
                    f"LLM={_format_latency(metrics.get('llm_latency_ms'))}, "
                    f"total={_format_latency(metrics.get('total_latency_ms'))}"
                )
                token_count = (
                    usage.get("total_tokens") if usage else None
                )
                cost = usage.get("cost_usd") if usage else None
                cost_text = f"${cost:.6f}" if cost is not None else "n/a"
                self.stdout.write(
                    f"{'':<24} tokens={token_count if token_count is not None else 'n/a'}, "
                    f"OpenRouter cost={cost_text}"
                )

            judge_usage = report["answer_judge_usage"]
            judge_tokens = judge_usage.get("total_tokens")
            judge_cost = judge_usage.get("cost_usd")
            judge_cost_text = (
                f"${judge_cost:.6f}" if judge_cost is not None else "n/a"
            )
            self.stdout.write(
                "Judge: "
                f"tokens={judge_tokens if judge_tokens is not None else 'n/a'}, "
                f"OpenRouter cost={judge_cost_text}"
            )
            total_usage = report["openrouter_usage"]["total"]
            total_tokens = total_usage.get("total_tokens")
            total_cost = total_usage.get("cost_usd")
            total_cost_text = (
                f"${total_cost:.6f}" if total_cost is not None else "n/a"
            )
            self.stdout.write(
                "All evaluation calls: "
                f"tokens={total_tokens if total_tokens is not None else 'n/a'}, "
                f"OpenRouter cost={total_cost_text}"
            )
        else:
            self.stdout.write(
                "Answer generation and LLM judging skipped "
                "(retrieval-only mode)."
            )

        if options["output"]:
            self.stdout.write(f"Full JSON report: {options['output']}")
