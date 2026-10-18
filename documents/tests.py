import json
import tempfile
from concurrent.futures import Future
from datetime import timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import httpx

from documents.services.citations import extract_citation_ids, validation_citations
from documents.services.context_optimizer import optimize_context, sort_context_results
from documents.services.evaluation import (
    calculate_hit_rate_at_k,
    calculate_ndcg_at_k,
    calculate_precision_at_k,
    calculate_recall_at_K,
    calculate_reciprocal_rank,
)
from documents.services.hybrid_retrieval import reciprocal_rank_fusion, search_hybrid_chunks
from documents.services.lexical_retrieval import search_lexical_chunks
from documents.services.neighbor_retrieval import expand_with_neighbors, get_neighbor_chunks
from documents.services.rag import answer_question
from documents.services.ingestion import process_document
from documents.services.chunking_service import process_document_chunks
from documents.services.llm import get_llm_client
from documents.services.llm import generate_answer
from documents.services.retrieval_evaluation import (
    evaluate_phase_10_dataset,
    evaluate_retrieval_dataset,
)
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.management import call_command, CommandError
from django.contrib.auth import get_user_model
from documents.services.reranker import rerank_results
from documents.services.retrieval import search_similar_chunks
from documents.services.indexing import process_document_indexing
from documents.services.pipeline import PipelineBusyError
from documents.services.vector_store import (
    _retry,
    delete_document_points,
    get_qdrant_client,
)
from httpx import patch
from documents.models import IndexingStatus
from documents.services.chunking import split_text
from documents.models import ChunkingStatus
from documents.models import DocumentChunk
from documents.admin import DocumentAdmin
from django.http import response
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock

from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import (
    Document,
    DocumentChatMessage,
    DocumentPage,
    DocumentStatus,
)
from documents.services.retrieval_quality import deduplicate_results, filter_by_score, limit_results, prepare_retrieval_results


class DocumentAPITests(APITestCase):

    def create_file(
        self,
        name="test.pdf",
        content=b"%PDF-1.4\nTest PDF contents",
    ):
        return SimpleUploadedFile(
            name=name,
            content=content,
            content_type="application/pdf",
        )

    def test_upload_document(self):

        file = self.create_file()

        response = self.client.post(
            "/api/documents/",
            {
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Document.objects.count(),
            1,
        )
        document = Document.objects.first()
        self.assertEqual(
            document.title,
            "test",
        )

        self.assertEqual(
            document.file_type,
            "pdf",
        )

        self.assertEqual(
            document.status,
            "UPLOADED",
        )

    def test_upload_unsupported_file(self):

        file = SimpleUploadedFile(
            "malware.exe",
            b"fake executable",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            "/api/documents/",
            {
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "file",
            response.data["error"]["message"],
        )

    def test_upload_rejects_mime_type_mismatch(self):
        uploaded = SimpleUploadedFile(
            "sample.txt",
            b"plain text",
            content_type="application/pdf",
        )

        response = self.client.post(
            "/api/documents/",
            {"file": uploaded},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)

    def test_upload_rejects_non_utf8_text(self):
        uploaded = SimpleUploadedFile(
            "sample.txt",
            b"\xff\xfe",
            content_type="text/plain",
        )

        response = self.client.post(
            "/api/documents/",
            {"file": uploaded},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)

    @override_settings(MAX_DOCUMENT_UPLOAD_BYTES=4)
    def test_upload_rejects_oversized_file(self):
        uploaded = SimpleUploadedFile(
            "sample.txt",
            b"12345",
            content_type="text/plain",
        )

        response = self.client.post(
            "/api/documents/",
            {"file": uploaded},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)

    def test_list_documents(self):

        file = self.create_file()

        self.client.post(
            "/api/documents/",
            {
                "file": file,
            },
            format="multipart",
        )

        response = self.client.get(
            "/api/documents/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    def test_get_document(self):

        file = self.create_file()

        create_response = self.client.post(
            "/api/documents/",
            {
                "file": file,
            },
            format="multipart",
        )

        document_id = create_response.data["id"]

        response = self.client.get(
            f"/api/documents/{document_id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            document_id,
        )

    def test_delete_document(self):

        file = self.create_file()

        create_response = self.client.post(
            "/api/documents/",
            {
                "file": file,
            },
            format="multipart",
        )

        document_id = create_response.data["id"]

        with patch(
            "documents.services.lifecycle.delete_document_points"
        ) as mock_delete_vectors:
            response = self.client.delete(
                f"/api/documents/{document_id}/"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        mock_delete_vectors.assert_called_once_with(document_id)

        self.assertEqual(
            Document.objects.count(),
            0,
        )

    def test_delete_retains_document_if_vector_cleanup_fails(self):
        create_response = self.client.post(
            "/api/documents/",
            {"file": self.create_file()},
            format="multipart",
        )
        document_id = create_response.data["id"]

        with patch(
            "documents.services.lifecycle.delete_document_points",
            side_effect=RuntimeError("Qdrant unavailable"),
        ):
            response = self.client.delete(
                f"/api/documents/{document_id}/"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        document = Document.objects.get(pk=document_id)
        self.assertEqual(document.status, DocumentStatus.DELETE_FAILED)
        self.assertTrue(document.file.storage.exists(document.file.name))


class DocumentPipelineAPITests(APITestCase):
    def test_retry_endpoint_only_schedules_failed_documents(self):
        document = Document.objects.create(
            title="Failed",
            file_type="txt",
            status=DocumentStatus.FAILED,
        )

        with patch(
            "documents.views.schedule_pipeline",
            return_value=document,
        ) as mock_schedule:
            response = self.client.post(
                f"/api/documents/{document.pk}/retry/"
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mock_schedule.assert_called_once_with(document.pk, retry=True)

    def test_pipeline_submission_returns_service_unavailable_when_busy(self):
        document = Document.objects.create(
            title="Busy",
            file_type="txt",
            status=DocumentStatus.UPLOADED,
        )

        with patch(
            "documents.views.schedule_pipeline",
            side_effect=PipelineBusyError("No worker capacity."),
        ):
            response = self.client.post(
                f"/api/documents/{document.pk}/process/"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(
            response.data["error"]["code"],
            "document_busy",
        )

    def test_second_pipeline_request_cannot_claim_same_document(self):
        document = Document.objects.create(
            title="Queued",
            file_type="txt",
            status=DocumentStatus.UPLOADED,
        )
        completed_future = Future()
        completed_future.set_result(None)

        with (
            patch(
                "documents.services.pipeline._executor.submit",
                return_value=completed_future,
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            from documents.services.pipeline import schedule_pipeline

            schedule_pipeline(document.pk)
            with self.assertRaises(PipelineBusyError):
                schedule_pipeline(document.pk)

    def test_retry_resets_incomplete_pipeline_stage_statuses(self):
        document = Document.objects.create(
            title="Failed stage",
            file_type="txt",
            status=DocumentStatus.FAILED,
            chunking_status=ChunkingStatus.PROCESSING,
            indexing_status=IndexingStatus.PROCESSING,
            indexed_chunk_count=3,
        )
        completed_future = Future()
        completed_future.set_result(None)

        with (
            patch(
                "documents.services.pipeline._executor.submit",
                return_value=completed_future,
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            from documents.services.pipeline import schedule_pipeline

            schedule_pipeline(document.pk, retry=True)

        document.refresh_from_db()
        self.assertEqual(document.status, DocumentStatus.PROCESSING)
        self.assertEqual(document.chunking_status, ChunkingStatus.PENDING)
        self.assertEqual(document.indexing_status, IndexingStatus.PENDING)
        self.assertEqual(document.indexed_chunk_count, 0)


class StaleDocumentRecoveryTests(TestCase):
    def test_recovery_marks_stale_stage_failed(self):
        document = Document.objects.create(
            title="Stale indexing",
            file_type="txt",
            status=DocumentStatus.INDEXING,
            indexing_status=IndexingStatus.PROCESSING,
            indexed_chunk_count=2,
            processing_started_at=timezone.now() - timedelta(minutes=2),
        )

        call_command(
            "recover_stale_documents",
            older_than=1,
            stdout=StringIO(),
        )

        document.refresh_from_db()
        self.assertEqual(document.status, DocumentStatus.FAILED)
        self.assertEqual(document.indexing_status, IndexingStatus.FAILED)
        self.assertEqual(document.indexed_chunk_count, 0)
        self.assertIsNone(document.processing_started_at)

    def test_recovery_rejects_non_positive_age(self):
        with self.assertRaises(CommandError):
            call_command("recover_stale_documents", older_than=0)


class DocumentIngestionTests(APITestCase):

    def upload_text_file(self,name="sample.txt",content=None):
        if content is None:
            content = b"This is a test document for RAG."

        file = SimpleUploadedFile(
            name,
            content,
            content_type="text/plain",
        )

        return self.client.post(
            "/api/documents/",
            {"file": file,},
            format="multipart",
        )

    def test_upload_document_starts_as_uploaded(self):
        response = self.upload_text_file()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "UPLOADED")
        self.assertEqual(response.data["title"], "sample")

    def test_process_text_document(self):
        response = self.upload_text_file()

        document_id = response.data["id"]

        document = Document.objects.get(pk=document_id)
        document.status = DocumentStatus.PROCESSING
        with patch(
            "documents.views.schedule_pipeline",
            return_value=document,
        ):
            process_response = self.client.post(
                f"/api/documents/{document_id}/process/"
            )

        self.assertEqual(
            process_response.status_code,
            status.HTTP_202_ACCEPTED,
        )
        self.assertEqual(
            process_response.data["status"],
            DocumentStatus.PROCESSING,
        )

        document = process_document(document_id)
        self.assertEqual(document.status, DocumentStatus.READY)
        self.assertEqual(document.page_count, 1)
        page = DocumentPage.objects.get(
            document_id=document_id,
            page_number=1,
        )
        self.assertEqual(
            page.content,
            "This is a test document for RAG.",
        )

    def test_get_extracted_pages(self):
        response = self.upload_text_file()
        document_id = response.data["id"]

        process_document(document_id)

        pages_response = self.client.get(
            f"/api/documents/{document_id}/pages/"
        )

        self.assertEqual(pages_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(pages_response.data), 1)
        self.assertEqual(
            pages_response.data[0]["content"],
            "This is a test document for RAG.",
        )

    def test_invalid_pdf_content_is_rejected_during_upload(self):
        file = SimpleUploadedFile(
            "broken.pdf",
            b"not a valid pdf",
            content_type="application/pdf",
        )

        upload_response = self.client.post(
            "/api/documents/",
            {"file": file},
            format="multipart",
        )

        self.assertEqual(
            upload_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Document.objects.count(), 0)

    def test_reprocess_document_replaces_pages(self):
        response = self.upload_text_file()
        document_id = response.data["id"]

        process_document(document_id)
        process_document(document_id)

        self.assertEqual(
            DocumentPage.objects.filter(
                document_id=document_id
            ).count(),
            1,
        )

class TextSplittingTests(APITestCase):
    def test_short_text_creates_one_chunk(self):
        chunks = list(split_text("Hello world", 500, 100))

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], "Hello world")

    def test_long_text_creates_multiple_chunks(self):
        text = "word " * 300
        chunks = list(split_text(text, 100, 20))

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c[0]) <= 100 for c in chunks))

    def test_chunks_have_overlap(self):
        text = "abcdefghij " * 30
        chunks = list(split_text(text, 50, 10))

        self.assertGreater(len(chunks), 1)

        first_end = chunks[0][2]
        second_start = chunks[1][1]

        self.assertLess(second_start, first_end)

    def test_invalid_chunk_size_raises_error(self):
        with self.assertRaises(ValueError):
            list(split_text("hello", 0, 0))

    def test_overlap_must_be_less_than_size(self):
        with self.assertRaises(ValueError):
            list(split_text("hello", 10, 10))

    def test_empty_text_returns_no_chunks(self):
        self.assertEqual(list(split_text("   \n  ", 100, 10)), [])


class DocumentChunkAPITests(APITestCase):
    def create_ready_document(self, content):
        uploaded = SimpleUploadedFile(
            "chunk-test.txt",
            content.encode("utf-8"),
            content_type="text/plain",
        )

        document = Document.objects.create(
            title="Chunk Test",
            file=uploaded,
            file_type="txt",
            status=DocumentStatus.READY,
        )

        page = DocumentPage.objects.create(
            document=document,
            page_number=1,
            content=content,
        )

        return document, page

    def test_manual_chunk_and_index_endpoints_are_removed(self):
        document, _ = self.create_ready_document("Test content.")

        chunk_response = self.client.post(
            f"/api/documents/{document.pk}/chunk/",
            {"chunk_size": 100, "chunk_overlap": 20},
            format="json",
        )
        index_response = self.client.post(
            f"/api/documents/{document.pk}/index/"
        )

        self.assertEqual(chunk_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(index_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chunks_keep_page_reference(self):
        document, page = self.create_ready_document(
            "This is content from page one. " * 20
        )
        process_document_chunks(
            document.pk,
            chunk_size=100,
            chunk_overlap=20,
        )

        chunk = DocumentChunk.objects.filter(
            document=document
        ).first()

        self.assertEqual(chunk.source_page_id, page.id)

    def test_list_chunks(self):
        document, _ = self.create_ready_document(
            "Example content. " * 20
        )
        process_document_chunks(
            document.pk,
            chunk_size=100,
            chunk_overlap=20,
        )

        response = self.client.get(
            f"/api/documents/{document.id}/chunks/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        self.assertIn("page_number", response.data[0])

    def test_reprocessing_does_not_duplicate_chunks(self):
        document, _ = self.create_ready_document(
            "Repeatable chunking test. " * 30
        )

        process_document_chunks(
            document.pk,
            chunk_size=100,
            chunk_overlap=20,
        )
        first_count = DocumentChunk.objects.filter(
            document=document
        ).count()
        process_document_chunks(
            document.pk,
            chunk_size=100,
            chunk_overlap=20,
        )
        second_count = DocumentChunk.objects.filter(
            document=document
        ).count()

        self.assertEqual(first_count, second_count)

class DocumentIndexingTests(APITestCase):
    def create_chunked_document(self):
        uploaded = SimpleUploadedFile(
            "index-test.txt",
            b"Test content for embedding.",
            content_type="text/plain",
        )

        document = Document.objects.create(
            title="Index Test",
            file=uploaded,
            file_type="txt",
            status=DocumentStatus.READY,
            chunking_status=ChunkingStatus.READY,
            chunk_count=2,
        )

        page = DocumentPage.objects.create(
            document=document,
            page_number=1,
            content="First chunk. Second chunk.",
        )

        DocumentChunk.objects.create(
            document=document,
            source_page=page,
            chunk_index=0,
            content="First chunk.",
            start_offset=0,
            end_offset=12,
        )

        DocumentChunk.objects.create(
            document=document,
            source_page=page,
            chunk_index=1,
            content="Second chunk.",
            start_offset=13,
            end_offset=26,
        )

        return document

    @patch("documents.services.indexing.get_qdrant_client")
    @patch("documents.services.indexing.embed_texts")
    def test_index_document(
        self,
        mock_embed_texts,
        mock_get_client,
    ):
        document = self.create_chunked_document()

        client = MagicMock()
        mock_get_client.return_value = client
        mock_embed_texts.return_value = [
            [0.1] * 384,
            [0.2] * 384,
        ]

        with patch(
            "documents.services.indexing.ensure_collection"
        ) as mock_ensure, patch(
            "documents.services.indexing.get_document_point_ids",
            return_value=[],
        ), patch(
            "documents.services.indexing.upsert_points"
        ) as mock_upsert:
            result = process_document_indexing(document.id)

        result.refresh_from_db()

        self.assertEqual(
            result.indexing_status,
            IndexingStatus.READY,
        )
        self.assertEqual(result.indexed_chunk_count, 2)
        mock_ensure.assert_called_once()
        mock_upsert.assert_called_once()
        client.close.assert_called_once()

    def test_cannot_index_unchunked_document(self):
        document = self.create_chunked_document()
        document.chunking_status = ChunkingStatus.PENDING
        document.save(update_fields=["chunking_status"])

        with self.assertRaises(ValueError):
            process_document_indexing(document.id)

    @patch("documents.services.indexing.get_qdrant_client")
    @patch("documents.services.indexing.embed_texts")
    def test_failed_indexing_updates_status(
        self,
        mock_embed_texts,
        mock_get_client,
    ):
        document = self.create_chunked_document()

        client = MagicMock()
        mock_get_client.return_value = client
        mock_embed_texts.side_effect = RuntimeError(
            "Embedding service unavailable"
        )

        with patch(
            "documents.services.indexing.ensure_collection"
        ), patch(
            "documents.services.indexing.get_document_point_ids",
            return_value=[],
        ):
            with self.assertRaises(RuntimeError):
                process_document_indexing(document.id)

        document.refresh_from_db()

        self.assertEqual(
            document.indexing_status,
            IndexingStatus.FAILED,
        )
        self.assertIn(
            "Embedding service unavailable",
            document.indexing_error,
        )
        client.close.assert_called_once()

    @patch("documents.services.indexing.delete_points")
    @patch("documents.services.indexing.get_document_point_ids")
    @patch("documents.services.indexing.get_qdrant_client")
    @patch("documents.services.indexing.embed_texts")
    def test_partial_indexing_failure_attempts_qdrant_cleanup(
        self,
        mock_embed_texts,
        mock_get_client,
        mock_get_point_ids,
        mock_delete_points,
    ):
        document = self.create_chunked_document()
        client = MagicMock()
        mock_get_client.return_value = client
        mock_get_point_ids.side_effect = [["old-point"], ["partial-point"]]
        mock_embed_texts.side_effect = RuntimeError("embedding failed")

        with patch("documents.services.indexing.ensure_collection"):
            with self.assertRaisesRegex(RuntimeError, "embedding failed"):
                process_document_indexing(document.pk)

        mock_delete_points.assert_called_once_with(
            client,
            ["partial-point"],
        )
        document.refresh_from_db()
        self.assertEqual(document.status, DocumentStatus.FAILED)
        self.assertEqual(document.indexed_chunk_count, 0)

class ExternalClientHardeningTests(SimpleTestCase):
    @override_settings(
        QDRANT_MAX_ATTEMPTS=2,
        QDRANT_RETRY_DELAY_SECONDS=0,
    )
    def test_qdrant_retry_retries_transport_failures(self):
        operation = MagicMock(
            side_effect=[
                httpx.ConnectError("temporary failure"),
                "success",
            ]
        )

        with patch("documents.services.vector_store.time.sleep"):
            result = _retry(operation, "argument")

        self.assertEqual(result, "success")
        self.assertEqual(operation.call_count, 2)

    @override_settings(
        QDRANT_URL="http://qdrant.test",
        QDRANT_API_KEY="test-key",
        QDRANT_TIMEOUT_SECONDS=7,
    )
    @patch("documents.services.vector_store.QdrantClient")
    def test_qdrant_client_receives_timeout(self, mock_client):
        get_qdrant_client()

        mock_client.assert_called_once_with(
            url="http://qdrant.test",
            api_key="test-key",
            timeout=7,
        )

    @override_settings(
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_BASE_URL="https://openrouter.test/api/v1",
        OPENROUTER_TIMEOUT_SECONDS=13,
        OPENROUTER_MAX_RETRIES=4,
    )
    @patch("documents.services.llm.OpenAI")
    def test_openrouter_client_receives_timeout_and_retry_count(
        self,
        mock_client,
    ):
        get_llm_client.cache_clear()
        try:
            get_llm_client()
        finally:
            get_llm_client.cache_clear()

        mock_client.assert_called_once_with(
            base_url="https://openrouter.test/api/v1",
            api_key="test-key",
            timeout=13,
            max_retries=4,
        )

    @patch("documents.services.vector_store.get_qdrant_client")
    def test_document_vector_cleanup_uses_payload_filter(
        self,
        mock_get_client,
    ):
        client = MagicMock()
        client.collection_exists.return_value = True
        mock_get_client.return_value = client

        delete_document_points(42)

        selector = client.delete.call_args.kwargs["points_selector"]
        self.assertEqual(
            selector.filter.must[0].key,
            "document_id",
        )
        self.assertEqual(
            selector.filter.must[0].match.value,
            42,
        )
        client.close.assert_called_once()


class RetrievalServiceTests(SimpleTestCase):

    @patch("documents.services.retrieval.get_qdrant_client")
    @patch("documents.services.retrieval.embed_texts")
    def test_search_returns_formatted_results(
        self,
        mock_embed,
        mock_get_client,
    ):
        mock_embed.return_value = [[0.1] * 384]

        client = MagicMock()
        mock_get_client.return_value = client
        client.collection_exists.return_value = True

        point = MagicMock()
        point.id = "point-uuid"
        point.score = 0.87
        point.payload = {
            "chunk_id": 5,
            "document_id": 2,
            "document_title": "Architecture",
            "page_number": 3,
            "chunk_index": 1,
            "content": "PostgreSQL stores application data.",
        }

        client.query_points.return_value = MagicMock(
            points=[point]
        )

        results = search_similar_chunks(
            query="Where is application data stored?",
            top_k=5,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], 5)
        self.assertEqual(results[0]["page_number"], 3)
        self.assertEqual(results[0]["score"], 0.87)
        client.close.assert_called_once()

    @patch("documents.services.retrieval.get_qdrant_client")
    @patch("documents.services.retrieval.embed_texts")
    def test_search_passes_document_filter(
        self,
        mock_embed,
        mock_get_client,
    ):
        mock_embed.return_value = [[0.1] * 384]

        client = MagicMock()
        mock_get_client.return_value = client
        client.collection_exists.return_value = True
        client.query_points.return_value = MagicMock(
            points=[]
        )

        results = search_similar_chunks(
            query="Database configuration",
            document_id=7,
        )

        self.assertEqual(results, [])

        kwargs = client.query_points.call_args.kwargs
        query_filter = kwargs["query_filter"]

        self.assertEqual(
            query_filter.must[0].key,
            "document_id",
        )
        self.assertEqual(
            query_filter.must[0].match.value,
            7,
        )

    def test_empty_query_raises_error(self):
        with self.assertRaises(ValueError):
            search_similar_chunks("  ")

    def test_invalid_top_k_raises_error(self):
        with self.assertRaises(ValueError):
            search_similar_chunks("test", top_k=100)

    def test_invalid_score_threshold_raises_error(self):
        with self.assertRaises(ValueError):
            search_similar_chunks(
                "test",
                score_threshold=1.5,
            )

    @patch("documents.services.retrieval.get_qdrant_client")
    @patch("documents.services.retrieval.embed_texts")
    def test_missing_collection_returns_empty_list(
        self,
        mock_embed,
        mock_get_client,
    ):
        mock_embed.return_value = [[0.1] * 384]

        client = MagicMock()
        mock_get_client.return_value = client
        client.collection_exists.return_value = False

        results = search_similar_chunks("test query")

        self.assertEqual(results, [])
        client.query_points.assert_not_called()
        client.close.assert_called_once()


class DocumentSearchAPITests(APITestCase):

    def create_indexed_document(self):
        file = SimpleUploadedFile(
            "search-test.txt",
            b"PostgreSQL is the database.",
            content_type="text/plain",
        )

        return Document.objects.create(
            title="Search Test",
            file=file,
            file_type="txt",
            status=DocumentStatus.READY,
            chunking_status=ChunkingStatus.READY,
            indexing_status=IndexingStatus.READY,
        )

    @patch("documents.views.search_similar_chunks")
    def test_search_api(self, mock_search):
        mock_search.return_value = [
            {
                "chunk_id": 1,
                "document_id": 1,
                "document_title": "Search Test",
                "page_number": 1,
                "chunk_index": 0,
                "content": "PostgreSQL is the database.",
                "score": 0.9,
            }
        ]

        response = self.client.post(
            "/api/documents/search/",
            {
                "query": "Which database is used?",
                "top_k": 5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result_count"], 1)
        self.assertEqual(
            response.data["results"][0]["chunk_id"],
            1,
        )

    def test_search_requires_query(self):
        response = self.client.post(
            "/api/documents/search/",
            {"top_k": 5},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_search_rejects_invalid_top_k(self):
        response = self.client.post(
            "/api/documents/search/",
            {
                "query": "test",
                "top_k": 100,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_search_rejects_unindexed_document(self):
        file = SimpleUploadedFile(
            "pending.txt",
            b"Some content",
            content_type="text/plain",
        )

        document = Document.objects.create(
            title="Not Indexed",
            file=file,
            file_type="txt",
            status=DocumentStatus.READY,
            chunking_status=ChunkingStatus.READY,
            indexing_status=IndexingStatus.PENDING,
        )

        response = self.client.post(
            "/api/documents/search/",
            {
                "query": "test",
                "document_id": document.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)

class GenerateAnswerTests(SimpleTestCase):

    @patch(
        "documents.services.llm.get_llm_client"
    )
    def test_generate_answer(self, mock_get_client):

        mock_response = MagicMock()

        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="The refund period is 30 days."
                )
            )
        ]
        mock_response.usage = None
        raw_response = MagicMock()
        raw_response.http_response.json.return_value = {}
        raw_response.parse.return_value = mock_response

        mock_client = MagicMock()

        mock_client.chat.completions.with_raw_response.create.return_value = (
            raw_response
        )

        mock_get_client.return_value = mock_client

        answer = generate_answer(
            system_prompt="You are a helpful assistant.",
            user_prompt="What is the refund period?",
        )

        self.assertEqual(
            answer,
            "The refund period is 30 days.",
        )

        mock_client.chat.completions.with_raw_response.create.assert_called_once()


class GenerateAnswerValidationTests(SimpleTestCase):

    def test_empty_system_prompt(self):
        with self.assertRaises(ValueError):
            generate_answer(
                system_prompt="",
                user_prompt="hello",
            )

    def test_empty_user_prompt(self):
        with self.assertRaises(ValueError):
            generate_answer(
                system_prompt="system",
                user_prompt="",
            )

class RAGQualityTests(
    SimpleTestCase
):

    @override_settings(RAG_MIN_SCORE=0.47)
    @patch(
        "documents.services.rag.generate_answer"
    )
    @patch(
        "documents.services.rag.search_hybrid_multi_query"
    )
    def test_default_score_threshold_uses_setting(
        self,
        mock_search,
        mock_generate,
    ):
        mock_search.return_value = []

        result = answer_question(
            query="What is the refund policy?"
        )

        self.assertEqual(
            mock_search.call_args.kwargs["score_threshold"],
            0.47,
        )
        self.assertEqual(
            result["retrieval"]["context_count"],
            0,
        )
        mock_generate.assert_not_called()

    @patch(
        "documents.services.rag.generate_answer"
    )
    @patch(
        "documents.services.rag.search_hybrid_multi_query"
    )
    @patch(
        "documents.services.rag.expand_with_neighbors",
        side_effect=lambda results, window: results,
    )
    @patch(
        "documents.services.rag.rerank_results"
    )
    def test_citations_are_validated(
        self,
        mock_rerank,
        mock_expand,
        mock_search,
        mock_generate,
    ):
        mock_rerank.side_effect = (
            lambda query, results, top_k: results[:top_k]
        )

        mock_search.return_value = [
            {
                "chunk_id": 10,
                "document_id": 1,
                "document_title": "Policy",
                "page_number": 4,
                "chunk_index": 2,
                "content": (
                    "Refunds are allowed within 30 days."
                ),
                "score": 0.91,
            }
        ]

        mock_generate.return_value = (
            "Refunds are allowed within 30 days [S1]."
        )

        result = answer_question(
            query="What is the refund policy?"
        )

        self.assertEqual(
            result["citations"][
                "cited_sources"
            ],
            ["S1"],
        )

        self.assertFalse(
            result["citations"][
                "has_invalid_citations"
            ]
        )

    @patch(
        "documents.services.rag.generate_answer"
    )
    @patch(
        "documents.services.rag.search_hybrid_multi_query"
    )
    @patch(
        "documents.services.rag.expand_with_neighbors",
        side_effect=lambda results, window: results,
    )
    @patch(
        "documents.services.rag.rerank_results"
    )
    def test_invalid_citation_is_detected(
        self,
        mock_rerank,
        mock_expand,
        mock_search,
        mock_generate,
    ):
        mock_rerank.side_effect = (
            lambda query, results, top_k: results[:top_k]
        )

        mock_search.return_value = [
            {
                "chunk_id": 10,
                "document_id": 1,
                "document_title": "Policy",
                "page_number": 4,
                "chunk_index": 2,
                "content": (
                    "Refunds are allowed within 30 days."
                ),
                "score": 0.91,
            }
        ]

        mock_generate.return_value = (
            "The company was founded in 2012 [S99]."
        )

        result = answer_question(
            query="When was the company founded?"
        )

        self.assertEqual(
            result["citations"][
                "invalid_citations"
            ],
            ["S99"],
        )

        self.assertTrue(
            result["citations"][
                "has_invalid_citations"
            ]
        )


class DocumentRAGAPITests(APITestCase):

    @override_settings(
        RAG_MIN_SCORE=0.30,
        RAG_MAX_CONTEXT_CHUNKS=4,
    )
    @patch(
        "documents.services.rag.generate_answer"
    )
    @patch(
        "documents.services.rag.search_hybrid_multi_query"
    )
    @patch(
        "documents.services.rag.expand_with_neighbors",
        side_effect=lambda results, window: results,
    )
    @patch(
        "documents.services.rag.rerank_results"
    )
    def test_rag_api_returns_limited_sources_and_validates_citations(
        self,
        mock_rerank,
        mock_expand,
        mock_search,
        mock_generate,
    ):
        user = get_user_model().objects.create_user(
            username="rag-user",
            password="test-password",
        )
        self.client.force_authenticate(user=user)
        mock_rerank.side_effect = (
            lambda query, results, top_k: results[:top_k]
        )
        mock_search.return_value = [
            {
                "chunk_id": chunk_id,
                "document_id": 1,
                "document_title": "Policy",
                "page_number": chunk_id,
                "chunk_index": chunk_id,
                "content": f"Policy detail {chunk_id}.",
                "score": score,
            }
            for chunk_id, score in enumerate(
                [0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.35],
                start=1,
            )
        ]
        mock_generate.return_value = (
            "The policy supports this answer [S1][S2][S99]."
        )

        response = self.client.post(
            "/api/documents/rag/",
            {
                "query": "What is the refund policy?",
                "top_k": 8,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["retrieval"]["retrieved_count"],
            7,
        )
        self.assertEqual(
            response.data["retrieval"]["candidate_count"],
            7,
        )
        self.assertEqual(
            response.data["retrieval"]["context_count"],
            4,
        )
        self.assertEqual(
            response.data["citations"],
            {
                "cited_sources": ["S1", "S2"],
                "invalid_citations": ["S99"],
                "citation_count": 2,
                "has_invalid_citations": True,
            },
        )
        self.assertEqual(
            [source["source_id"] for source in response.data["sources"]],
            ["S1", "S2", "S3", "S4"],
        )
        self.assertEqual(
            mock_search.call_args.kwargs["score_threshold"],
            0.30,
        )

    def test_document_scoped_rag_saves_and_returns_owned_chat_history(self):
        user = get_user_model().objects.create_user(
            username="chat-user",
            password="test-password",
        )
        document = Document.objects.create(
            owner=user,
            title="Policy",
            file="documents/policy.pdf",
            file_type="pdf",
            status=DocumentStatus.READY,
            indexing_status=IndexingStatus.READY,
        )
        self.client.force_authenticate(user=user)
        answer = {
            "query": "What is the refund policy?",
            "answer": "Refunds are available within 30 days.",
            "sources": [],
            "citations": {},
            "retrieval": {},
        }

        with patch("documents.views.answer_question", return_value=answer):
            response = self.client.post(
                "/api/documents/rag/",
                {
                    "query": "What is the refund policy?",
                    "document_id": document.pk,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history_response = self.client.get(
            f"/api/documents/{document.pk}/chat-history/"
        )
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [(message["role"], message["content"]) for message in history_response.data],
            [
                ("user", "What is the refund policy?"),
                ("assistant", "Refunds are available within 30 days."),
            ],
        )
        self.assertEqual(
            DocumentChatMessage.objects.filter(document=document).count(),
            2,
        )

        other_user = get_user_model().objects.create_user(
            username="other-chat-user",
            password="test-password",
        )
        self.client.force_authenticate(user=other_user)
        self.assertEqual(
            self.client.get(
                f"/api/documents/{document.pk}/chat-history/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )


class CitationValidationTests(
    SimpleTestCase
):

    def test_valid_citations(self):

        answer = (
            "Refunds are available [S1]."
        )

        sources = [
            {
                "source_id": "S1"
            },
            {
                "source_id": "S2"
            },
        ]

        result = validation_citations(
            answer,
            sources,
        )

        self.assertEqual(
            result["cited_sources"],
            ["S1"],
        )

        self.assertEqual(
            result["invalid_citations"],
            [],
        )

        self.assertFalse(
            result["has_invalid_citations"]
        )

    def test_invalid_citation(self):

        answer = (
            "The company was founded in 2012 [S99]."
        )

        sources = [
            {
                "source_id": "S1"
            },
            {
                "source_id": "S2"
            },
        ]

        result = validation_citations(
            answer,
            sources,
        )

        self.assertEqual(
            result["cited_sources"],
            [],
        )

        self.assertEqual(
            result["invalid_citations"],
            ["S99"],
        )

        self.assertTrue(
            result["has_invalid_citations"]
        )


class CitationExtractionTests(
    SimpleTestCase
):

    def test_extract_citations(self):

        answer = (
            "Refunds are available for 30 days [S1]. "
            "Proof of purchase is required [S2]."
        )

        citations = extract_citation_ids(
            answer
        )

        self.assertEqual(
            citations,
            ["S1", "S2"],
        )

    def test_duplicate_citations(self):

        answer = (
            "Refunds are available [S1]. "
            "The policy states [S1]."
        )

        citations = extract_citation_ids(
            answer
        )

        self.assertEqual(
            citations,
            ["S1"],
        )

class RetrievalQualityTests(
    SimpleTestCase
):

    def test_filter_by_score(self):

        results = [
            {
                "chunk_id": 1,
                "score": 0.90,
            },
            {
                "chunk_id": 2,
                "score": 0.40,
            },
            {
                "chunk_id": 3,
                "score": 0.20,
            },
        ]

        filtered = filter_by_score(
            results,
            minimum_score=0.30,
        )

        self.assertEqual(
            len(filtered),
            2,
        )

    def test_deduplicate_results(self):

        results = [
            {
                "chunk_id": 1,
                "score": 0.90,
            },
            {
                "chunk_id": 1,
                "score": 0.80,
            },
            {
                "chunk_id": 2,
                "score": 0.70,
            },
        ]

        deduplicated = deduplicate_results(
            results
        )

        self.assertEqual(
            len(deduplicated),
            2,
        )

    def test_limit_results(self):

        results = [
            {"chunk_id": 1},
            {"chunk_id": 2},
            {"chunk_id": 3},
        ]

        limited = limit_results(
            results,
            limit=2,
        )

        self.assertEqual(
            len(limited),
            2,
        )

    def test_complete_pipeline(self):

        results = [
            {
                "chunk_id": 1,
                "score": 0.90,
            },
            {
                "chunk_id": 1,
                "score": 0.89,
            },
            {
                "chunk_id": 2,
                "score": 0.70,
            },
            {
                "chunk_id": 3,
                "score": 0.20,
            },
        ]

        processed = prepare_retrieval_results(
            results,
            minimum_score=0.30,
            max_results=2,
        )

        self.assertEqual(
            len(processed),
            2,
        )

        self.assertEqual(
            processed[0]["chunk_id"],
            1,
        )

        self.assertEqual(
            processed[1]["chunk_id"],
            2,
        )

class RetrievalEvaluationTests(
    SimpleTestCase
):

    def test_recall(self):

        score = calculate_recall_at_K(
            expected_chunk_ids=[
                10,
                20,
            ],
            retrieved_chunk_ids=[
                10,
                20,
                30,
                40,
            ],
        )

        self.assertEqual(
            score,
            1.0,
        )

    def test_partial_recall(self):

        score = calculate_recall_at_K(
            expected_chunk_ids=[
                10,
                20,
            ],
            retrieved_chunk_ids=[
                10,
                30,
            ],
        )

        self.assertEqual(
            score,
            0.5,
        )

    def test_recall_is_zero_when_no_expected_chunks_are_retrieved(self):
        score = calculate_recall_at_K(
            expected_chunk_ids=[10, 20],
            retrieved_chunk_ids=[30, 40],
        )

        self.assertEqual(score, 0.0)

    def test_precision(self):

        score = calculate_precision_at_k(
            expected_chunk_ids=[
                10,
                20,
            ],
            retrieved_chunk_ids=[
                10,
                20,
                30,
                40,
            ],
        )

        self.assertEqual(
            score,
            0.5,
        )

    def test_precision_at_k_uses_requested_k_as_denominator(self):
        score = calculate_precision_at_k(
            expected_chunk_ids=[10],
            retrieved_chunk_ids=[10, 20],
            k=5,
        )

        self.assertEqual(score, 0.2)

    def test_hit_rate_at_k(self):
        self.assertEqual(
            calculate_hit_rate_at_k(
                expected_chunk_ids=[10, 20],
                retrieved_chunk_ids=[30, 20, 40],
                k=2,
            ),
            1.0,
        )

    def test_ndcg_at_k_rewards_relevant_chunks_at_higher_ranks(self):
        score = calculate_ndcg_at_k(
            expected_chunk_ids=[10, 20],
            retrieved_chunk_ids=[10, 30, 20],
            k=3,
        )

        self.assertAlmostEqual(score, 0.9197207891481876)

class RerankerTests(
    SimpleTestCase
):

    @patch(
        "documents.services.reranker.get_reranker"
    )
    def test_rerank_results(
        self,
        mock_get_reranker,
    ):

        mock_model = MagicMock()

        mock_model.predict.return_value = [
            0.20,
            0.95,
            0.50,
        ]

        mock_get_reranker.return_value = (
            mock_model
        )

        results = [
            {
                "chunk_id": 1,
                "content": "Some unrelated text.",
                "score": 0.80,
            },
            {
                "chunk_id": 2,
                "content": "Refund policy information.",
                "score": 0.70,
            },
            {
                "chunk_id": 3,
                "content": "Shipping information.",
                "score": 0.60,
            },
        ]

        reranked = rerank_results(
            query="What is the refund policy?",
            results=results,
            top_k=2,
        )

        self.assertEqual(
            len(reranked),
            2,
        )

        self.assertEqual(
            reranked[0]["chunk_id"],
            2,
        )

        self.assertEqual(
            reranked[0]["rerank_score"],
            0.95,
        )

        self.assertEqual(
            reranked[1]["chunk_id"],
            3,
        )

    def test_empty_results(self):

        result = rerank_results(
            query="What is the refund policy?",
            results=[],
            top_k=5,
        )

        self.assertEqual(
            result,
            [],
        )

    def test_empty_query(self):

        with self.assertRaises(
            ValueError
        ):
            rerank_results(
                query="",
                results=[
                    {
                        "chunk_id": 1,
                        "content": "Some text.",
                    }
                ],
            )

    def test_reciprocal_rank(self):

        score = calculate_reciprocal_rank(
            expected_chunk_ids=[42],
            retrieved_chunk_ids=[
                10,
                20,
                42,
            ],
        )

        self.assertAlmostEqual(
            score,
            1 / 3,
        )


    def test_reciprocal_rank_first_result(self):

        score = calculate_reciprocal_rank(
            expected_chunk_ids=[42],
            retrieved_chunk_ids=[
                42,
                10,
                20,
            ],
        )

        self.assertEqual(
            score,
            1.0,
        )


class LexicalRetrievalTests(
    TestCase
):

    def setUp(self):

        self.document = Document.objects.create(
            title="Company Policy",
            file=SimpleUploadedFile(
                "company-policy.txt",
                b"Company policy test document.",
                content_type="text/plain",
            ),
            file_type="txt",
        )

        refund_page = DocumentPage.objects.create(
            document=self.document,
            page_number=1,
            content=(
                "Customers can request a refund "
                "within 30 days."
            ),
        )
        shipping_page = DocumentPage.objects.create(
            document=self.document,
            page_number=2,
            content="Shipping usually takes five days.",
        )

        DocumentChunk.objects.create(
            document=self.document,
            source_page=refund_page,
            content=refund_page.content,
            start_offset=0,
            end_offset=len(refund_page.content),
            chunk_index=0,
        )

        DocumentChunk.objects.create(
            document=self.document,
            source_page=shipping_page,
            content=shipping_page.content,
            start_offset=0,
            end_offset=len(shipping_page.content),
            chunk_index=1,
        )

    def test_exact_keyword_search(self):

        results = search_lexical_chunks(
            query="refund",
            top_k=5,
        )

        self.assertGreater(
            len(results),
            0,
        )

        self.assertIn(
            "refund",
            results[0]["content"].lower(),
        )

class RRFTests(
    SimpleTestCase
):

    def test_rrf_combines_results(self):

        dense = [
            {
                "chunk_id": 1,
                "content": "A",
                "score": 0.9,
            },
            {
                "chunk_id": 2,
                "content": "B",
                "score": 0.8,
            },
            {
                "chunk_id": 3,
                "content": "C",
                "score": 0.7,
            },
        ]

        lexical = [
            {
                "chunk_id": 2,
                "content": "B",
                "lexical_score": 1.0,
            },
            {
                "chunk_id": 1,
                "content": "A",
                "lexical_score": 0.8,
            },
            {
                "chunk_id": 4,
                "content": "D",
                "lexical_score": 0.7,
            },
        ]

        results = (
            reciprocal_rank_fusion(
                dense_results=dense,
                lexical_results=lexical,
                k=60,
            )
        )

        self.assertEqual(
            len(results),
            4,
        )

        # Chunk 1 and 2 appear in
        # both retrieval systems.
        self.assertIn(
            results[0]["chunk_id"],
            [1, 2],
        )

    def test_chunk_found_by_both_gets_boost(self):

        dense = [
            {
                "chunk_id": 1,
            },
        ]

        lexical = [
            {
                "chunk_id": 1,
            },
        ]

        results = (
            reciprocal_rank_fusion(
                dense_results=dense,
                lexical_results=lexical,
            )
        )

        self.assertEqual(
            len(results),
            1,
        )

        expected = (
            1 / 61
            +
            1 / 61
        )

        self.assertAlmostEqual(
            results[0]["rrf_score"],
            expected,
        )

class HybridRetrievalTests(
    SimpleTestCase
):

    @patch(
        "documents.services.hybrid_retrieval.search_lexical_chunks"
    )
    @patch(
        "documents.services.hybrid_retrieval.search_similar_chunks"
    )
    def test_hybrid_search(
        self,
        mock_dense,
        mock_lexical,
    ):

        mock_dense.return_value = [
            {
                "chunk_id": 1,
                "content": "Semantic result",
                "score": 0.8,
            }
        ]

        mock_lexical.return_value = [
            {
                "chunk_id": 1,
                "content": "Exact keyword result",
                "lexical_score": 1.0,
            },
            {
                "chunk_id": 2,
                "content": "Keyword result",
                "lexical_score": 0.5,
            },
        ]

        results = search_hybrid_chunks(
            query="refund policy",
            top_k=10,
        )

        self.assertEqual(
            len(results),
            2,
        )

        self.assertEqual(
            results[0]["chunk_id"],
            1,
        )

        self.assertIsNotNone(
            results[0]["rrf_score"]
        )

        self.assertEqual(
            results[0]["dense_rank"],
            1,
        )

        self.assertEqual(
            results[0]["lexical_rank"],
            1,
        )


    @patch(
        "documents.services.rag.search_hybrid_multi_query"
    )
    @patch(
        "documents.services.rag.expand_with_neighbors",
        side_effect=lambda results, window: results,
    )
    @patch(
        "documents.services.rag.rerank_results"
    )
    @patch(
        "documents.services.rag.generate_answer"
    )
    def test_hybrid_rag_pipeline(
        self,
        mock_generate,
        mock_rerank,
        mock_expand,
        mock_hybrid,
    ):

        mock_hybrid.return_value = [
            {
                "chunk_id": 1,
                "document_id": 1,
                "document_title": "Policy",
                "page_number": 2,
                "content": (
                    "Refunds are allowed within 30 days."
                ),
                "score": 0.8,
                "lexical_score": 1.2,
                "rrf_score": 0.032,
                "dense_rank": 2,
                "lexical_rank": 1,
            }
        ]

        mock_rerank.return_value = [
            {
                "chunk_id": 1,
                "document_id": 1,
                "document_title": "Policy",
                "page_number": 2,
                "content": (
                    "Refunds are allowed within 30 days."
                ),
                "score": 0.8,
                "lexical_score": 1.2,
                "rrf_score": 0.032,
                "dense_rank": 2,
                "lexical_rank": 1,
                "rerank_score": 7.2,
            }
        ]

        mock_generate.return_value = (
            "Refunds are allowed within 30 days [S1]."
        )

        result = answer_question(
            query="What is the refund policy?"
        )

        self.assertEqual(
            result["retrieval"]["context_count"],
            1,
        )

        self.assertEqual(
            result["citations"]["cited_sources"],
            ["S1"],
        )
        self.assertEqual(
            result["sources"][0]["dense_rank"],
            2,
        )
        self.assertEqual(
            result["sources"][0]["lexical_rank"],
            1,
        )
        self.assertEqual(
            result["sources"][0]["rrf_score"],
            0.032,
        )
        self.assertEqual(
            result["sources"][0]["dense_score"],
            0.8,
        )
        self.assertEqual(
            result["sources"][0]["lexical_score"],
            1.2,
        )


class RetrievalDatasetEvaluationTests(
    SimpleTestCase
):

    @patch(
        "documents.services.retrieval_evaluation.search_hybrid_chunks"
    )
    @patch(
        "documents.services.retrieval_evaluation.search_similar_chunks"
    )
    def test_compares_dense_and_hybrid_metrics(
        self,
        mock_dense,
        mock_hybrid,
    ):
        dataset = [
            {
                "question": "First question?",
                "expected_chunk_ids": [10, 11],
            },
            {
                "question": "Second question?",
                "expected_chunk_ids": [20],
            },
        ]
        dense_results_by_query = {
            "First question?": [10, 30, 40, 50, 60],
            "Second question?": [20, 21],
        }
        dense_result_batches = []
        hybrid_results_by_query = {
            "First question?": [30, 11, 10, 40, 50],
            "Second question?": [99, 20],
        }

        def make_dense_results(query, **kwargs):
            results = [
                {"chunk_id": chunk_id}
                for chunk_id in dense_results_by_query[query]
            ]
            dense_result_batches.append(results)
            return results

        mock_dense.side_effect = make_dense_results
        mock_hybrid.side_effect = (
            lambda query, dense_results, **kwargs: [
                {"chunk_id": chunk_id}
                for chunk_id in hybrid_results_by_query[query]
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            dataset_path = Path(directory) / "questions.json"
            dataset_path.write_text(
                json.dumps(dataset),
                encoding="utf-8",
            )

            report = evaluate_retrieval_dataset(
                dataset_path=dataset_path,
                top_k=5,
                score_threshold=0.3,
            )

        self.assertEqual(report["question_count"], 2)
        self.assertEqual(
            report["averages"]["dense"],
            {
                "recall_at_k": 0.75,
                "precision_at_k": 0.35,
                "mrr": 1.0,
            },
        )
        self.assertEqual(
            report["averages"]["hybrid"],
            {
                "recall_at_k": 1.0,
                "precision_at_k": 0.45,
                "mrr": 0.5,
            },
        )
        self.assertEqual(
            mock_hybrid.call_args_list[0].kwargs["dense_results"],
            dense_result_batches[0],
        )
        self.assertEqual(
            mock_hybrid.call_args_list[1].kwargs["dense_results"],
            dense_result_batches[1],
        )

    def test_rejects_invalid_dataset_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset_path = Path(directory) / "questions.json"
            dataset_path.write_text(
                json.dumps(
                    [{"question": "Question?", "expected_chunk_ids": []}]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "expected_chunk_ids",
            ):
                evaluate_retrieval_dataset(
                    dataset_path=dataset_path,
                )


class Phase10EvaluationTests(SimpleTestCase):

    def test_evaluates_pipeline_metrics_citations_and_usage(self):
        dataset = [
            {
                "id": 1,
                "question": "What is RAG?",
                "expected_chunk_ids": [1],
                "reference_answer": "RAG retrieves relevant context.",
                "expected_citations": [1],
            }
        ]
        result = [
            {
                "chunk_id": 1,
                "document_id": 2,
                "document_title": "Test",
                "page_number": 1,
                "content": "RAG retrieves relevant context.",
            }
        ]
        usage = {
            "prompt_tokens": 2,
            "completion_tokens": 3,
            "total_tokens": 5,
            "cost_usd": 0.01,
        }
        judge_scores = {
            strategy: {
                "correctness": 1.0,
                "relevance": 0.9,
                "faithfulness": 1.0,
                "rationale": "Supported by the context.",
            }
            for strategy in ("A", "B", "C", "D", "E")
        }

        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "documents.services.retrieval_evaluation.search_similar_chunks",
                return_value=result,
            ),
            patch(
                "documents.services.retrieval_evaluation.search_hybrid_chunks",
                return_value=result,
            ),
            patch(
                "documents.services.retrieval_evaluation.rerank_results",
                return_value=result,
            ),
            patch(
                "documents.services.retrieval_evaluation.analyze_query_with_usage",
                return_value=(
                    SimpleNamespace(
                        rewritten_query="RAG",
                        expanded_queries=[],
                    ),
                    usage,
                ),
            ),
            patch(
                "documents.services.retrieval_evaluation.search_hybrid_multi_query",
                return_value=result,
            ),
            patch(
                "documents.services.retrieval_evaluation.expand_with_neighbors",
                return_value=result,
            ),
            patch(
                "documents.services.retrieval_evaluation.sort_context_results",
                side_effect=lambda results: results,
            ),
            patch(
                "documents.services.retrieval_evaluation.optimize_context",
                side_effect=lambda results, **kwargs: results,
            ),
            patch(
                "documents.services.retrieval_evaluation.generate_answer_with_usage",
                side_effect=[
                    ("A grounded answer [S1]", usage),
                    ("A grounded answer [S1]", usage),
                    ("Unsupported citation [S99]", usage),
                    ("A grounded answer [S1]", usage),
                    ("A grounded answer [S1]", usage),
                ],
            ),
            patch(
                "documents.services.retrieval_evaluation._judge_answers",
                return_value=(
                    judge_scores,
                    {
                        "prompt_tokens": 7,
                        "completion_tokens": 1,
                        "total_tokens": 8,
                        "cost_usd": 0.02,
                    },
                ),
            ),
        ):
            dataset_path = Path(directory) / "questions.json"
            dataset_path.write_text(
                json.dumps(dataset),
                encoding="utf-8",
            )
            report = evaluate_phase_10_dataset(
                dataset_path=dataset_path,
                evaluate_answers=True,
            )

        self.assertEqual(report["strategies_run"], ["A", "B", "C", "D", "E"])
        self.assertEqual(
            report["averages"]["A"]["recall_at_5"],
            1.0,
        )
        self.assertEqual(
            report["averages"]["A"]["precision_at_5"],
            0.2,
        )
        self.assertEqual(
            report["averages"]["A"]["answer_relevance"],
            0.9,
        )
        self.assertEqual(
            report["averages"]["A"]["faithfulness"],
            1.0,
        )
        self.assertEqual(
            report["questions"][0]["strategies"]["A"]["citation_correct"],
            True,
        )
        self.assertEqual(
            report["questions"][0]["strategies"]["C"][
                "invalid_citation_ids"
            ],
            ["S99"],
        )
        self.assertEqual(
            report["questions"][0]["strategies"]["C"]["citation_precision"],
            0.0,
        )
        self.assertEqual(
            report["questions"][0]["strategies"]["C"]["citation_correct"],
            False,
        )
        self.assertEqual(
            report["openrouter_usage"]["total"]["total_tokens"],
            38,
        )
        self.assertAlmostEqual(
            report["openrouter_usage"]["total"]["cost_usd"],
            0.08,
        )

class NeighborRetrievalTests(
    TestCase
):

    def setUp(self):

        self.document = (
            Document.objects.create(
                title="Test Document",
                file_type="txt",
            )
        )
        self.page = DocumentPage.objects.create(
            document=self.document,
            page_number=1,
            content="Chunk 0 Chunk 1 Chunk 2 Chunk 3 Chunk 4",
        )

        for index in range(5):

            DocumentChunk.objects.create(
                document=self.document,
                source_page=self.page,
                chunk_index=index,
                content=f"Chunk {index}",
                start_offset=index * 8,
                end_offset=index * 8 + 7,
            )

    def test_get_neighbors(self):

        middle_chunk = (
            DocumentChunk.objects.get(
                document=self.document,
                chunk_index=2,
            )
        )

        results = get_neighbor_chunks(
            chunk_id=middle_chunk.id,
            window=1,
        )

        chunk_indexes = [
            item["chunk_index"]
            for item in results
        ]

        self.assertEqual(
            chunk_indexes,
            [1, 2, 3],
        )

    def test_expand_with_neighbors(self):

        middle_chunk = (
            DocumentChunk.objects.get(
                document=self.document,
                chunk_index=2,
            )
        )

        results = [
            {
                "chunk_id": middle_chunk.id,
                "chunk_index": 2,
                "content": "Chunk 2",
                "rerank_score": 5.0,
            }
        ]

        expanded = expand_with_neighbors(
            results,
            window=1,
        )

        indexes = sorted(
            item["chunk_index"]
            for item in expanded
        )

        self.assertEqual(
            indexes,
            [1, 2, 3],
        )

class ContextOptimizerTests(
    SimpleTestCase
):

    def test_primary_chunks_first(self):

        results = [
            {
                "chunk_id": 2,
                "rerank_score": 2.0,
                "is_neighbor": True,
            },
            {
                "chunk_id": 1,
                "rerank_score": 5.0,
                "is_neighbor": False,
            },
        ]

        sorted_results = (
            sort_context_results(
                results
            )
        )

        self.assertEqual(
            sorted_results[0][
                "chunk_id"
            ],
            1,
        )

    def test_context_limit(self):

        results = [
            {
                "chunk_id": 1,
                "is_neighbor": False,
                "rerank_score": 5,
            },
            {
                "chunk_id": 2,
                "is_neighbor": False,
                "rerank_score": 4,
            },
            {
                "chunk_id": 3,
                "is_neighbor": True,
                "rerank_score": 2,
            },
        ]

        optimized = optimize_context(
            results,
            max_chunks=2,
        )

        self.assertEqual(
            len(optimized),
            2,
        )