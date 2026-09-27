from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .qdrant import get_qdrant_client

@api_view(['GET'])
def health_check(request):
    services = {}

    #-----------------------
    # DJango
    #-----------------------
    services['django'] = "ok"

    #-----------------------
    # Postgres
    #-----------------------
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            services["postgres"] = "ok"
    except Exception as exc:
        services["postgres"] = {
            "status" : "error",
            "error"  : str(exc)
        }

    #-----------------------
    # Qdrant
    #-----------------------
    try:
        client = get_qdrant_client()
        client.get_collections()
        services["qdrant"] = "ok"
    except Exception as e:
        services["qdrant"] = {
            "status" : "error",
            "error"  : str(e)
        }

    all_healthy = all(
        value == "ok"
        for value in services.values()
    )    

    return Response(
        {
            "status": "ok" if all_healthy else "degraded",
            "services": services
        },
        status=200 if all_healthy else 503,
    )