from documents.admin import DocumentAdmin
from django.http import response
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

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