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