from numpy.core import records
from django.conf import settings
from qdrant_client import QdrantClient,models

def get_qdrant_client():
    return QdrantClient(
        url = settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    
def ensure_collection(client):
    collection = settings.QDRANT_COLLECTION

    if not client.collection_exists(collection):
        client.create_collection(
            collection_name = collection,
            vectors_config=models.VectorParams(
                size = settings.EMBEDDING_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        return 

    info = client.get_collection(collection)
    config = info.config.params.vectors 

    if not isinstance(config, models.VectorParams):
        raise ValueError("Expected a single unnamed dense vector configuration")

    if config.size != settings.EMBEDDING_DIMENSION:
        raise ValueError(
            "Qdrant collection dimension does not match the "
            "configured embedding dimension."
        )

def upsert_points(client,points):
    if points:
        client.upsert(
            collection_name = settings.QDRANT_COLLECTION,
            points=points,
            wait=True,
        )

def delete_points(client, point_ids):
    if point_ids:
        client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=models.PointIdsList(
                points=point_ids
            ),
            wait=True,
        )

def get_document_point_ids(client,document_id):
    """Return existing Qdrant point IDs document"""
    point_ids = []
    offset = None 

    while True:
        records, offset = client.scroll(
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