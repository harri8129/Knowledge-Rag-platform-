import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from documents.services.retrieval_evaluation import (
    evaluate_phase_10_dataset,
)


class Command(BaseCommand):
    help = (
        "Evaluate the five Phase 10 retrieval strategies against a golden "
        "dataset."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default=str(
                settings.BASE_DIR
                / "documents"
                / "evaluation"
                / "questions.json"
            ),
            help="Path to a JSON dataset of question/expected chunk IDs.",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="Maximum results to score per query (default: 5).",
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
            help="Override dataset document IDs and restrict retrieval to this document.",
        )
        parser.add_argument(
            "--answers",
            action="store_true",
            help=(
                "Generate and judge answers for all strategies. This sends "
                "questions and retrieved passages to the configured OpenRouter model."
            ),
        )
        parser.add_argument(
            "--through-reranking",
            action="store_true",
            help=(
                "Run only Dense, Hybrid, and Hybrid + reranking; skips "
                "query rewriting and neighbors."
            ),
        )

    def handle(self, *args, **options):
        dataset_path = Path(options["dataset"])

        try:
            report = evaluate_phase_10_dataset(
                dataset_path=dataset_path,
                top_k=options["top_k"],
                score_threshold=options["score_threshold"],
                document_id=options["document_id"],
                evaluate_answers=options["answers"],
                include_rewriting=not options["through_reranking"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            json.dumps(report, indent=2)
        )
