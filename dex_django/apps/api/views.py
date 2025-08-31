from __future__ import annotations
from django.http import JsonResponse
from django.http import HttpResponse


def health(request):
    """Lightweight health probe."""
    return JsonResponse({"ok": True, "service": "django", "ws": "channels-ready"})





def index(request):
    """Root route."""
    return JsonResponse({"ok": True, "service": "django", "routes": ["/health"]})




def favicon(request):
    """Stub favicon to avoid 404 noise in dev."""
    return HttpResponse(b"", content_type="image/x-icon", status=204)
