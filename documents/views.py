from documents.services.rag import answer_question
from documents.serializers import RAGRequestSerializer
from drf_spectacular.utils import extend_schema
from documents.services.chunking_service import process_document_chunks
from documents.models import DocumentChunk
from documents.serializers import DocumentChunkSerializer
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document, DocumentPage, IndexingStatus
from documents.serializers import (
    DocumentSerializer,
    DocumentPageSerializer,
    RetrievalRequestSerializer
)
from documents.services.ingestion import process_document
from documents.services.indexing import process_document_indexing
from documents.services.retrieval import search_similar_chunks
import logging

logger = logging.getLogger(__name__)

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

class DocumentIndexView(APIView):
    def post(self,request,pk):
        document = get_object_or_404(Document,pk=pk)

        try:
            document = process_document_indexing(document.id)
        
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            document.refresh_from_db()

            return Response(
                {
                    "detail": "Indexing failed.",
                    "indexing_status": document.indexing_status,
                    "indexing_error": document.indexing_error,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )        

        return Response(
            DocumentSerializer(
                document,
                context={
                    "request":request
                },
            ).data,
            status=status.HTTP_200_OK,
        )        

class DocumentSearchView(APIView):

    @extend_schema(
        request=RetrievalRequestSerializer,
        description="Search indexed documents using semantic similarity.",
        responses={200: None},
    )

    def post(self,request):
        serializer = RetrievalRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        document_id = data.get("document_id")

        if document_id is not None:

            try:
                document = Document.objects.get(id=document_id)
            except Document.DoesNotExist:
                return Response(
                    {"detail": "Document not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            if document.indexing_status != IndexingStatus.READY:
                return Response(
                    {"detail": ("Document is not indexed"),
                     "indexing_status":document.indexing_status, 
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        
        try:
            results = search_similar_chunks(
                query=data["query"],
                top_k=data["top_k"],
                score_threshold=data.get("score_threshold"),
                document_id=document_id,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:
            import traceback

            traceback.print_exc()

            return Response(
                {"detail": "Retrieval failed",
                "error":str(exc),
                "type":type(exc).__name__,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response(
            {
                "query": data["query"],
                "top_k": data["top_k"],
                "result_count": len(results),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

class DocumentRAGView(APIView):

    @extend_schema(
        request=RAGRequestSerializer,
        description="Perform RAG on indexed documents to answer a query.",
        responses={200: None},
    )

    def post(self,request):
        serializer = RAGRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["query"]
        top_k = serializer.validated_data["top_k"]
        score_threshold = serializer.validated_data["score_threshold"]
        document_id = serializer.validated_data["document_id"]

       # -----------------------------------------
       # Optional document-specific validation
       # -----------------------------------------

        if document_id is not None:

            try:
                document = Document.objects.get(id=document_id)
            except Document.DoesNotExist:
                return Response(
                    {"detail": "Document not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            if document.indexing_status != "ready":
                return Response(
                    {
                        "detail": (
                            "Document is not ready for RAG queries."
                        ),
                        "indexing_status": document.indexing_status,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        try:
            results = answer_question(
                query=query,
                top_k=top_k,
                score_threshold=score_threshold,
                document_id=document_id,
            )
        
        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:

            logger.exception("RAG generation failure")

            return Response(
                {
                    "detail": str(exc),
                    "error_type": type(exc).__name__,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            results,
            status=status.HTTP_200_OK,
        )