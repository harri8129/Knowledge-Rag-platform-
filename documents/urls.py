from documents.views import DocumentChunkListView,DocumentChunkProcessView
from django.urls import path

from .views import DocumentDetailView, DocumentListCreateView, DocumentPageListView, DocumentProcessView

urlpatterns = [
    path("", DocumentListCreateView.as_view(), name="document-list-create"),
    path("<int:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("<int:pk>/process/",DocumentProcessView.as_view(),name="document-process"),
    path("<int:pk>/pages/",DocumentPageListView.as_view(),name="document=pages"),
    path("<int:pk>/chunk/",DocumentChunkProcessView.as_view(),name="document-chunk-process",),
    path("<int:pk>/chunks/",DocumentChunkListView.as_view(),name="document-chunk-list",),
]