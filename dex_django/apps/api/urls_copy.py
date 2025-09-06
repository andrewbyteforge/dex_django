# APP: Django
# FILE: apps/api/urls_copy.py
from django.urls import path
from django.http import JsonResponse

# Create simple placeholder views for copy trading endpoints
def copy_status(request):
    """Placeholder for copy trading status."""
    return JsonResponse({"status": "ok", "message": "Copy trading status endpoint"})

def copy_traders(request):
    """Placeholder for copy traders list."""
    return JsonResponse({"status": "ok", "traders": []})

def copy_trades(request):
    """Placeholder for copy trades list."""
    return JsonResponse({"status": "ok", "trades": []})

def discovery_status(request):
    """Placeholder for discovery status."""
    return JsonResponse({"status": "ok", "discovery_active": False})

urlpatterns = [
    path('copy/status', copy_status, name='copy_status'),
    path('copy/traders', copy_traders, name='copy_traders'),
    path('copy/trades', copy_trades, name='copy_trades'),
    path('discovery/discovery-status', discovery_status, name='discovery_status'),
]