from documents.services.citations import extract_citation_ids, validation_citations
from documents.services.evaluation import calculate_precision_at_k, calculate_recall_at_K, calculate_reciprocal_rank
from documents.services.rag import answer_question
from documents.services.llm import generate_answer
from django.test import SimpleTestCase, override_settings
from documents.services.reranker import rerank_results
from documents.services.retrieval import search_similar_chunks
from documents.services.indexing import process_document_indexing
from httpx import patch
from documents.models import IndexingStatus
from documents.services.chunking import split_text
from documents.models import ChunkingStatus
from documents.models import DocumentChunk
from documents.admin import DocumentAdmin
from django.http import response
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest.mock import patch, MagicMock

from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document, DocumentPage, DocumentStatus
from documents.services.retrieval_quality import deduplicate_results, filter_by_score, limit_results, prepare_retrieval_results


class DocumentAPITests(APITestCase):

    def create_file(
        self,
        name="test.pdf",
        content=b"test content",
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
            response.data,
        )

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

        print("Create status:", create_response.status_code)
        print("Create data:", create_response.data)

        document_id = create_response.data["id"]

        print("Document ID:", document_id)
        print("Database count:", Document.objects.count())

        response = self.client.delete(
            f"/api/documents/{document_id}/"
        )

        print("Detail status:", response.status_code)
        print("Detail data:", response.data)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertEqual(
            Document.objects.count(),
            0,
        )


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

        process_response = self.client.post(
            f"/api/documents/{document_id}/process/"
        )

        self.assertEqual(
            process_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            process_response.data["status"],
            DocumentStatus.READY,
        )
        self.assertEqual(
            process_response.data["page_count"],
            1,
        )

        page = DocumentPage.objects.get(document_id=document_id,page_number=1)
        self.assertEqual(
            page.content,
            "This is a test document for RAG.",
        )

    def test_get_extracted_pages(self):
        response = self.upload_text_file()
        document_id = response.data["id"]

        self.client.post(
            f"/api/documents/{document_id}/process/"
        )

        pages_response = self.client.get(
            f"/api/documents/{document_id}/pages/"
        )

        self.assertEqual(pages_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(pages_response.data), 1)
        self.assertEqual(
            pages_response.data[0]["content"],
            "This is a test document for RAG.",
        )

    def test_processing_invalid_pdf_marks_failed(self):
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

        document_id = upload_response.data["id"]

        process_response = self.client.post(
            f"/api/documents/{document_id}/process/"
        )

        self.assertEqual(
            process_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        document = Document.objects.get(id=document_id)
        self.assertEqual(document.status, DocumentStatus.FAILED)
        self.assertTrue(document.processing_error)

    def test_reprocess_document_replaces_pages(self):
        response = self.upload_text_file()
        document_id = response.data["id"]

        self.client.post(
            f"/api/documents/{document_id}/process/"
        )
        self.client.post(
            f"/api/documents/{document_id}/process/"
        )

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

    def test_generate_chunks(self):
        content = "This is a test. " * 50
        document, _ = self.create_ready_document(content)

        response = self.client.post(
            f"/api/documents/{document.id}/chunk/",
            {"chunk_size": 100, "chunk_overlap": 20},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        document.refresh_from_db()
        self.assertEqual(
            document.chunking_status,
            ChunkingStatus.READY,
        )
        self.assertGreater(document.chunk_count, 1)
        self.assertEqual(
            DocumentChunk.objects.filter(document=document).count(),
            document.chunk_count,
        )

    def test_chunks_keep_page_reference(self):
        document, page = self.create_ready_document(
            "This is content from page one. " * 20
        )

        response = self.client.post(
            f"/api/documents/{document.id}/chunk/",
            {"chunk_size": 100, "chunk_overlap": 20},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        chunk = DocumentChunk.objects.filter(
            document=document
        ).first()

        self.assertEqual(chunk.source_page_id, page.id)

    def test_list_chunks(self):
        document, _ = self.create_ready_document(
            "Example content. " * 20
        )

        self.client.post(
            f"/api/documents/{document.id}/chunk/",
            {"chunk_size": 100, "chunk_overlap": 20},
            format="json",
        )

        response = self.client.get(
            f"/api/documents/{document.id}/chunks/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        self.assertIn("page_number", response.data[0])

    def test_cannot_chunk_unprocessed_document(self):
        uploaded = SimpleUploadedFile(
            "pending.txt",
            b"Unprocessed document",
            content_type="text/plain",
        )

        document = Document.objects.create(
            title="Pending",
            file=uploaded,
            file_type="txt",
            status=DocumentStatus.UPLOADED,
        )

        response = self.client.post(
            f"/api/documents/{document.id}/chunk/",
            {"chunk_size": 100, "chunk_overlap": 20},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_reprocessing_does_not_duplicate_chunks(self):
        document, _ = self.create_ready_document(
            "Repeatable chunking test. " * 30
        )

        url = f"/api/documents/{document.id}/chunk/"
        payload = {"chunk_size": 100, "chunk_overlap": 20}

        first_response = self.client.post(
            url, payload, format="json"
        )
        first_count = DocumentChunk.objects.filter(
            document=document
        ).count()

        second_response = self.client.post(
            url, payload, format="json"
        )
        second_count = DocumentChunk.objects.filter(
            document=document
        ).count()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
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

    @patch("documents.views.process_document_indexing")
    def test_indexing_api(self, mock_process):
        document = self.create_chunked_document()
        document.indexing_status = IndexingStatus.READY
        document.indexed_chunk_count = 2
        mock_process.return_value = document

        response = self.client.post(
            f"/api/documents/{document.id}/index/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["indexing_status"],
            IndexingStatus.READY,
        )

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

        mock_client = MagicMock()

        mock_client.chat.completions.create.return_value = (
            mock_response
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

        mock_client.chat.completions.create.assert_called_once()


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
        "documents.services.rag.search_similar_chunks"
    )
    def test_default_score_threshold_uses_setting(
        self,
        mock_search,
        mock_generate,
    ):
        mock_search.return_value = [
            {
                "chunk_id": 10,
                "document_id": 1,
                "document_title": "Policy",
                "page_number": 4,
                "chunk_index": 2,
                "content": "Refunds are allowed within 30 days.",
                "score": 0.46,
            }
        ]

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
        "documents.services.rag.search_similar_chunks"
    )
    @patch(
        "documents.services.rag.rerank_results"
    )
    def test_citations_are_validated(
        self,
        mock_rerank,
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
        "documents.services.rag.search_similar_chunks"
    )
    @patch(
        "documents.services.rag.rerank_results"
    )
    def test_invalid_citation_is_detected(
        self,
        mock_rerank,
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
        "documents.services.rag.search_similar_chunks"
    )
    @patch(
        "documents.services.rag.rerank_results"
    )
    def test_rag_api_returns_limited_sources_and_validates_citations(
        self,
        mock_rerank,
        mock_search,
        mock_generate,
    ):
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
                [0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.35, 0.20],
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
            response.data["retrieval"],
            {
                "retrieved_count": 8,
                "candidate_count": 7,
                "context_count": 4,
            },
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