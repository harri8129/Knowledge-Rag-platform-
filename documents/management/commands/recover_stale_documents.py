from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from documents.models import (
    ChunkingStatus,
    Document,
    DocumentStatus,
    IndexingStatus,
)


class Command(BaseCommand):
    help = (
        "Mark document operations left active by a crashed worker as failed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than",
            type=int,
            default=settings.DOCUMENT_OPERATION_STALE_SECONDS,
            help="Only recover operations older than this many seconds.",
        )

    def handle(self, *args, **options):
        older_than = options["older_than"]
        if older_than < 1:
            raise CommandError("--older-than must be greater than zero.")

        cutoff = timezone.now() - timedelta(seconds=older_than)
        active_statuses = (
            DocumentStatus.PROCESSING,
            DocumentStatus.CHUNKING,
            DocumentStatus.INDEXING,
            DocumentStatus.DELETING,
        )
        stale_documents = Document.objects.filter(
            status__in=active_statuses,
            processing_started_at__lt=cutoff,
        )

        stale_count = 0
        for document in stale_documents.iterator():
            if document.status == DocumentStatus.DELETING:
                new_status = DocumentStatus.DELETE_FAILED
                message = (
                    "Deletion worker stopped before completion. "
                    "Retry document deletion."
                )
            else:
                new_status = DocumentStatus.FAILED
                message = (
                    "Processing worker stopped before completion. "
                    "Retry document processing."
                )

            updated = Document.objects.filter(
                pk=document.pk,
                status=document.status,
                processing_started_at__lt=cutoff,
            )
            updates = {
                "status": new_status,
                "processing_error": message,
                "processing_started_at": None,
            }
            if document.status == DocumentStatus.CHUNKING:
                updates.update(
                    chunking_status=ChunkingStatus.FAILED,
                    chunking_error=message,
                )
            elif document.status == DocumentStatus.INDEXING:
                updates.update(
                    indexing_status=IndexingStatus.FAILED,
                    indexing_error=message,
                    indexed_chunk_count=0,
                )
            updated = updated.update(**updates)
            stale_count += updated

        self.stdout.write(
            self.style.SUCCESS(
                f"Marked {stale_count} stale document operation(s) for retry."
            )
        )
