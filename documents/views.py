from documents.services.chunking_service import process_document_chunks
from documents.models import DocumentChunk
from documents.serializers import DocumentChunkSerializer
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


class DocumentChunkProcessView(APIView):
    def post(self,request,pk):
        document = get_object_or_404(Document,pk=pk)

        try:
            chunk_size = int(request.data.get("chunk_size",500))
            chunk_overlap = int(request.data.get("chunk_overlap",100))

            if chunk_size <= 0 or chunk_size > 10000:
                return Response(
                    {"detail": "chunk_size must be between 1 and 10000."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if chunk_overlap < 0 or chunk_overlap >= chunk_size:
                return Response(
                    {
                        "detail": (
                            "chunk_overlap must be >= 0 "
                            "and less than chunk_size."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            document = process_document_chunks(
                document_id=document.id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            document.refresh_from_db()
            return Response(
                {
                    "detail": "Chunk generation failed.",
                    "chunking_status": document.chunking_status,
                    "chunking_error": document.chunking_error,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            DocumentSerializer(
                document,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class DocumentChunkListView(generics.ListAPIView):
    serializer_class = DocumentChunkSerializer

    def get_queryset(self):
        document_id = self.kwargs["pk"]

        get_object_or_404(Document, pk=document_id)

        return (
            DocumentChunk.objects
            .filter(document_id=document_id)
            .select_related("source_page", "document")
            .order_by("chunk_index")
        )                  