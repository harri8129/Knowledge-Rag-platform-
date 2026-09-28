from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Document


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