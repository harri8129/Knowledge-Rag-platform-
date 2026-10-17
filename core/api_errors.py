import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        view = context.get("view")
        logger.exception(
            "Unhandled API exception",
            extra={
                "view": view.__class__.__name__ if view else "unknown",
                "stage": "api",
            },
        )
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                }
            },
            status=500,
        )

    response.data = {
        "error": {
            "code": "request_error",
            "message": response.data,
        }
    }
    return response
