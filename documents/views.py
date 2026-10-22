from documents.services.rag import answer_question
from documents.serializers import RAGRequestSerializer
from drf_spectacular.utils import OpenApiResponse, extend_schema
from documents.models import DocumentChunk
from documents.serializers import DocumentChunkSerializer
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction

from documents.models import (
    Document,
    DocumentChatMessage,
    DocumentPage,
    IndexingStatus,
)
from documents.models import DocumentStatus
from documents.serializers import (
    DocumentSerializer,
    DocumentPageSerializer,
    DocumentChatMessageSerializer,
    RetrievalRequestSerializer
)
from documents.services.retrieval import search_similar_chunks
import logging
from documents.services.lifecycle import (
    DocumentDeletionError,
    delete_document,
)
from documents.services.pipeline import (
    PipelineBusyError,
    schedule_pipeline,
)

logger = logging.getLogger(__name__)

class DocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Return only documents owned by the current user."""
        return Document.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        """Automatically assign the uploading user as owner."""
        serializer.save(owner=self.request.user)


class DocumentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        try:
            delete_document(document.pk)
        except ValueError as exc:
            return Response(
                {
                    "error": {
                        "code": "document_busy",
                        "message": str(exc),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        except DocumentDeletionError:
            return Response(
                {
                    "error": {
                        "code": "document_deletion_failed",
                        "message": "Document deletion could not be completed.",
                    }
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentProcessView(APIView):

    @extend_schema(
        request=None,
        responses={
            202: DocumentSerializer,
            409: OpenApiResponse(description="Document cannot be processed."),
            503: OpenApiResponse(description="Processing capacity is full."),
        },
    )
    def post(self, request, pk):
        # Ownership check — 404 for foreign or non-existent documents
        if not Document.objects.filter(pk=pk, owner=request.user).exists():
            return Response(
                {"error": {"code": "document_not_found", "message": "Document not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            document = schedule_pipeline(pk)
        except Document.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "document_not_found",
                        "message": "Document not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PipelineBusyError as exc:
            return Response(
                {
                    "error": {
                        "code": "document_busy",
                        "message": str(exc),
                    }
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as exc:
            return Response(
                {
                    "error": {
                        "code": "document_invalid_state",
                        "message": str(exc),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            DocumentSerializer(
                document, context={"request": request}
            ).data,
            status=status.HTTP_202_ACCEPTED,
        )


class DocumentRetryView(APIView):
    def post(self, request, pk):
        # Ownership check
        if not Document.objects.filter(pk=pk, owner=request.user).exists():
            return Response(
                {"error": {"code": "document_not_found", "message": "Document not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            document = schedule_pipeline(pk, retry=True)
        except Document.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "document_not_found",
                        "message": "Document not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PipelineBusyError as exc:
            return Response(
                {
                    "error": {
                        "code": "document_busy",
                        "message": str(exc),
                    }
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as exc:
            return Response(
                {
                    "error": {
                        "code": "document_invalid_state",
                        "message": str(exc),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            DocumentSerializer(document).data,
            status=status.HTTP_202_ACCEPTED,
        )


class DocumentPageListView(generics.ListAPIView):
    serializer_class = DocumentPageSerializer

    def get_queryset(self):
        document_id = self.kwargs["pk"]
        # Scope to current user — 404 for foreign documents
        get_object_or_404(Document, pk=document_id, owner=self.request.user)
        return DocumentPage.objects.filter(
            document_id=document_id
        ).order_by("page_number")


class DocumentChunkListView(generics.ListAPIView):
    serializer_class = DocumentChunkSerializer

    def get_queryset(self):
        document_id = self.kwargs["pk"]
        # Scope to current user
        get_object_or_404(Document, pk=document_id, owner=self.request.user)
        return (
            DocumentChunk.objects
            .filter(document_id=document_id)
            .select_related("source_page", "document")
            .order_by("chunk_index")
        )                  


class DocumentChatHistoryView(generics.ListAPIView):
    serializer_class = DocumentChatMessageSerializer

    def get_queryset(self):
        document = get_object_or_404(
            Document,
            pk=self.kwargs["pk"],
            owner=self.request.user,
        )
        return DocumentChatMessage.objects.filter(document=document)


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
                document = Document.objects.get(id=document_id, owner=request.user)
            except Document.DoesNotExist:
                return Response(
                    {"error": {
                        "code": "document_not_found",
                        "message": "Document not found.",
                    }},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            if (
                document.status != DocumentStatus.READY
                or document.indexing_status != IndexingStatus.READY
            ):
                return Response(
                    {"error": {
                        "code": "document_not_ready",
                        "message": "Document is not indexed.",
                        "indexing_status": document.indexing_status,
                    }},
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
                {"error": {
                    "code": "invalid_retrieval_request",
                    "message": str(exc),
                }},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            logger.exception(
                "Document retrieval failed",
                extra={"stage": "retrieval"},
            )
            return Response(
                {"error": {
                    "code": "retrieval_failed",
                    "message": "Retrieval failed.",
                }
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
        score_threshold = serializer.validated_data.get(
            "score_threshold"
        )
        document_id = serializer.validated_data.get(
            "document_id"
        )

       # -----------------------------------------
       # Optional document-specific validation
       # -----------------------------------------

        if document_id is not None:

            try:
                document = Document.objects.get(id=document_id, owner=request.user)
            except Document.DoesNotExist:
                return Response(
                    {"error": {
                        "code": "document_not_found",
                        "message": "Document not found.",
                    }},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            if (
                document.status != DocumentStatus.READY
                or document.indexing_status != IndexingStatus.READY
            ):
                return Response(
                    {
                        "error": {
                            "code": "document_not_ready",
                            "message": "Document is not ready for RAG queries.",
                            "indexing_status": document.indexing_status,
                        }
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
                    "error": {
                        "code": "invalid_rag_request",
                        "message": str(exc),
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception(
                "RAG generation failure",
                extra={"stage": "generation"},
            )

            return Response(
                {
                    "error": {
                        "code": "rag_generation_failed",
                        "message": "Answer generation failed.",
                    }
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if document_id is not None:
            cited_ids = set(
                (results.get("citations") or {}).get("cited_sources", [])
            )
            cited_sources = [
                source
                for source in results.get("sources", [])
                if source.get("source_id") in cited_ids
            ]
            with transaction.atomic():
                DocumentChatMessage.objects.bulk_create(
                    [
                        DocumentChatMessage(
                            document=document,
                            role=DocumentChatMessage.Role.USER,
                            content=query,
                        ),
                        DocumentChatMessage(
                            document=document,
                            role=DocumentChatMessage.Role.ASSISTANT,
                            content=results["answer"],
                            citations=cited_sources,
                        ),
                    ]
                )

        return Response(
            results,
            status=status.HTTP_200_OK,
        )