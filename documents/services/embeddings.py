from functools import lru_cache 

from django.conf import settings
from fastembed import TextEmbedding

@lru_cache(maxsize=1)   # lru cache insure model is loaded once per django process rather than reloaded for every api request
def get_embedding_model():
    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def embed_texts(texts:list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = get_embedding_model()
    
    vectors = [
        vector.tolist()
        for vector in model.embed(texts)
    ]

    if len(vectors) != len(texts):
        raise RuntimeError("Embedding model returned an unexpecteed vector count")

    for vector in vectors:
        if len(vector) != settings.EMBEDDING_DIMENSION:
            raise ValueError(
                f"Expected {settings.EMBEDDING_DIMENSION} dimensions, got ,"
                f"got {len(vector)}."
            )

    return vectors