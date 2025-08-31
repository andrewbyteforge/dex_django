from __future__ import annotations

from typing import Callable
from django.http import JsonResponse
from django.conf import settings
import logging
import time
import uuid
from django.http import JsonResponse

logger = logging.getLogger("api")


class ApiKeyAuthMiddleware:
    """
    Very small API key gate for /api/ paths.
    Enabled when settings.API_AUTH_ENABLED is True and settings.API_KEY is set.
    Clients must send:  X-API-Key: <key>
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request):
        # Only guard API routes
        if request.path.startswith("/api/"):
            if getattr(settings, "API_AUTH_ENABLED", False):
                required = getattr(settings, "API_KEY", "")
                provided = request.headers.get("X-API-Key", "")
                if not required or provided != required:
                    return JsonResponse({"detail": "Invalid or missing API key."}, status=401)
        return self.get_response(request)


import logging
import time
import uuid
from django.http import JsonResponse

logger = logging.getLogger("api")


class ApiRequestLogMiddleware:
    """
    Logs every API request with timing and trace_id.
    Catches unhandled exceptions and returns JSON error.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = str(uuid.uuid4())[:8]
        request.trace_id = trace_id

        start = time.time()
        try:
            response = self.get_response(request)
        except Exception:
            logger.exception("Unhandled exception [trace=%s]", trace_id)
            return JsonResponse(
                {"ok": False, "detail": "Internal server error", "trace_id": trace_id},
                status=500,
            )

        # attach trace id on all API responses
        try:
            if request.path.startswith("/api/"):
                response["X-Trace-Id"] = trace_id
        except Exception:
            pass

        duration = (time.time() - start) * 1000
        logger.info("API %s %s [%s] %d ms", request.method, request.path, trace_id, duration)
        return response
