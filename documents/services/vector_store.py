import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from django.conf import settings
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)
_Result = TypeVar("_Result")


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=settings.QDRANT_TIMEOUT_SECONDS,
    )


def _retry(
    operation: Callable[..., _Result],
    *args: Any,
    **kwargs: Any,
) -> _Result:
    operation_name = getattr(
        operation,
        "__name__",
        operation.__class__.__name__,
    )
    for attempt in range(settings.QDRANT_MAX_ATTEMPTS):
        try:
            return operation(*args, **kwargs)
        except UnexpectedResponse as exc:
            if exc.status_code not in (429, 500, 502, 503, 504):
                raise
            if attempt + 1 == settings.QDRANT_MAX_ATTEMPTS:
                raise
            logger.warning(
                "Transient Qdrant response; retrying",
                extra={
                    "operation": operation_name,
                    "attempt": attempt + 1,
                    "status_code": exc.status_code,
                },
            )
        except httpx.TransportError:
            if attempt + 1 == settings.QDRANT_MAX_ATTEMPTS:
                raise
            logger.warning(
                "Transient Qdrant transport error; retrying",
                extra={
                    "operation": operation_name,
                    "attempt": attempt + 1,
                },
            )
        time.sleep(settings.QDRANT_RETRY_DELAY_SECONDS * (2 ** attempt))


def ensure_collection(client):
    collection = settings.QDRANT_COLLECTION

    if not _retry(client.collection_exists, collection):
        try:
            _retry(
                client.create_collection,
                collection_name=collection,
                vectors_config=models.VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=models.Distance.COSINE,
                ),
            )
        except UnexpectedResponse as exc:
            if exc.status_code != 409:
                raise

    info = _retry(client.get_collection, collection)
    if info is None:
        raise RuntimeError("Qdrant returned no collection information.")
    config = info.config.params.vectors
    if config is None:
        raise ValueError("Qdrant collection has no vector configuration.")

    if not isinstance(config, models.VectorParams):
        raise ValueError("Expected a single unnamed dense vector configuration")

    if config.size != settings.EMBEDDING_DIMENSION:
        raise ValueError(
            "Qdrant collection dimension does not match the "
            "configured embedding dimension."
        )

def upsert_points(client,points):
    if points:
        _retry(
            client.upsert,
            collection_name = settings.QDRANT_COLLECTION,
            points=points,
            wait=True,
        )

def delete_points(client, point_ids):
    if point_ids:
        _retry(
            client.delete,
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=models.PointIdsList(
                points=point_ids
            ),
            wait=True,
        )


def collection_exists(client: QdrantClient, collection_name: str) -> bool:
    return _retry(client.collection_exists, collection_name)


def query_points(client: QdrantClient, **kwargs: Any) -> Any:
    return _retry(client.query_points, **kwargs)


def get_document_point_ids(client,document_id):
    """Return existing Qdrant point IDs document"""
    point_ids = []
    offset = None 

    while True:
        records, offset = _retry(
            client.scroll,
            collection_name = settings.QDRANT_COLLECTION,
            scroll_filter = models.Filter(
                must = [
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            ),
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )

        point_ids.extend(record.id for record in records)

        if offset is None:
            break

    return point_ids


def delete_document_points(document_id: int) -> None:
    client = get_qdrant_client()
    try:
        if not collection_exists(client, settings.QDRANT_COLLECTION):
            return

        _retry(
            client.delete,
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
    finally:
        client.close()