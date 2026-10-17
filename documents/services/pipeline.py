import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Callable

from django.db import close_old_connections, transaction
from django.utils import timezone

from documents.models import (
    ChunkingStatus,
    Document,
    DocumentStatus,
    IndexingStatus,
)
from documents.services.chunking_service import process_document_chunks
from documents.services.indexing import process_document_indexing
from documents.services.ingestion import process_document
from documents.services.vector_store import delete_document_points

logger = logging.getLogger(__name__)

_MAX_WORKERS = 2
_executor = ThreadPoolExecutor(
    max_workers=_MAX_WORKERS,
    thread_name_prefix="document-pipeline",
)
_capacity = BoundedSemaphore(_MAX_WORKERS)

_BUSY_STATUSES = {
    DocumentStatus.PROCESSING,
    DocumentStatus.CHUNKING,
    DocumentStatus.INDEXING,
    DocumentStatus.DELETING,
}


class PipelineBusyError(Exception):
    pass


def _mark_failed(document_id: int, error: str) -> None:
    Document.objects.filter(pk=document_id).update(
        status=DocumentStatus.FAILED,
        processing_error=error[:4000],
        processing_started_at=None,
    )


def _run_pipeline(document_id: int) -> None:
    close_old_connections()
    try:
        # Remove vectors before replacing their backing chunks. This favors
        # consistency over availability: the document is temporarily absent
        # from retrieval while it is being rebuilt.
        delete_document_points(document_id)
        Document.objects.filter(pk=document_id).update(
            indexing_status=IndexingStatus.PENDING,
            indexed_chunk_count=0,
        )

        process_document(document_id, claimed=True)

        Document.objects.filter(pk=document_id).update(
            status=DocumentStatus.CHUNKING
        )
        process_document_chunks(document_id, claimed=True)

        Document.objects.filter(pk=document_id).update(
            status=DocumentStatus.INDEXING,
        )
        process_document_indexing(document_id, claimed=True)

        Document.objects.filter(pk=document_id).update(
            status=DocumentStatus.READY,
            processing_error="",
            processing_started_at=None,
        )
        logger.info(
            "Document pipeline completed",
            extra={"document_id": document_id, "stage": "ready"},
        )
    except Exception as exc:
        logger.exception(
            "Document pipeline failed",
            extra={"document_id": document_id, "stage": "pipeline"},
        )
        _mark_failed(document_id, str(exc))
    finally:
        close_old_connections()


def _submit_operation(
    document_id: int,
    stage: str,
    operation: Callable[..., None],
    *args: object,
) -> None:
    try:
        future = _executor.submit(operation, document_id, *args)
    except Exception as exc:
        _capacity.release()
        logger.exception(
            "Could not start document operation",
            extra={"document_id": document_id, "stage": stage},
        )
        _mark_failed(document_id, str(exc))
        return

    future.add_done_callback(lambda _: _capacity.release())


def schedule_pipeline(document_id: int, *, retry: bool = False) -> Document:
    if not _capacity.acquire(blocking=False):
        raise PipelineBusyError(
            "Document processing is at capacity. Try again later."
        )

    callback_started = False
    try:
        with transaction.atomic():
            document = Document.objects.select_for_update().get(
                pk=document_id
            )

            if document.status in _BUSY_STATUSES:
                raise PipelineBusyError(
                    "This document already has an operation in progress."
                )

            if retry:
                if document.status != DocumentStatus.FAILED:
                    raise ValueError(
                        "Only failed document processing can be retried."
                    )
            elif document.status != DocumentStatus.UPLOADED:
                raise ValueError(
                    "Only an uploaded document can start this pipeline."
                )

            document.status = DocumentStatus.PROCESSING
            document.processing_error = ""
            document.chunking_status = ChunkingStatus.PENDING
            document.chunking_error = ""
            document.indexing_status = IndexingStatus.PENDING
            document.indexing_error = ""
            document.indexed_chunk_count = 0
            document.processing_started_at = timezone.now()
            document.attempt_count += 1
            document.save(
                update_fields=[
                    "status",
                    "processing_error",
                    "chunking_status",
                    "chunking_error",
                    "indexing_status",
                    "indexing_error",
                    "indexed_chunk_count",
                    "processing_started_at",
                    "attempt_count",
                    "updated_at",
                ]
            )
            def submit_after_commit() -> None:
                nonlocal callback_started
                callback_started = True
                _submit_pipeline(document_id)

            transaction.on_commit(
                submit_after_commit,
                robust=True,
            )
        return document
    except Exception:
        if not callback_started:
            _capacity.release()
        raise


def _submit_pipeline(document_id: int) -> None:
    _submit_operation(document_id, "pipeline", _run_pipeline)