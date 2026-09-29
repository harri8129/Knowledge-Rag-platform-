from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document, DocumentPage
from documents.serializers import (
    DocumentSerializer,
    DocumentPageSerializer,
)
from documents.services.ingestion import process_document

class DocumentListCreateView(generics.ListCreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]


class DocumentDetailView(generics.RetrieveDestroyAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

class DocumentProcessView(APIView):

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        try:
            document = process_document(document.id)
        except ValueError as exc:
            return Response(
                {"detail":str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            document.refresh_from_db()
            return Response(
                {
                    "detail": "Document processing failed",
                    "status": document.status,
                    "processing_error": document.processing_error,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DocumentSerializer(
                document,
                context={"request":request},
            ).data,
            status=status.HTTP_200_OK,
        )

class DocumentPageListView(generics.ListAPIView):
    serializer_class = DocumentPageSerializer

    def get_queryset(self):
        document_id = self.kwargs["pk"]

        get_object_or_404(Document, pk=document_id)

        return DocumentPage.objects.filter(
            document_id=document_id
        ).order_by("page_number")
