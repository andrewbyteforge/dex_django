from __future__ import annotations

from typing import Any, Optional
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework.request import Request


def exception_handler(exc: Exception, context: dict[str, Any]) -> Optional[Response]:
    """
    Wrap DRF errors into a consistent schema and include trace_id (from middleware).
    """
    response = drf_exception_handler(exc, context)
    request: Optional[Request] = context.get("request")  # type: ignore[assignment]
    trace_id = getattr(request, "trace_id", None) if request is not None else None

    if response is not None:
        # Ensure a consistent body
        data = {
            "ok": False,
            "detail": response.data if isinstance(response.data, dict) else {"error": response.data},
            "trace_id": trace_id,
        }
        response.data = data
        if trace_id:
            response["X-Trace-Id"] = trace_id
        return response

    # For non-DRF exceptions, let our middleware handle 500s
    return None
