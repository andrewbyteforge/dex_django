# APP: backend
# FILE: dex_django/apps/api/views_api_v1.py
from __future__ import annotations

import csv
from io import BytesIO
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.utils.timezone import now
from django.conf import settings
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.storage.models import Provider, Token, Pair, Trade, LedgerEntry
from .serializers import (
    ProviderSerializer,
    TokenSerializer,
    PairSerializer,
    TradeSerializer,
    LedgerEntrySerializer,
)


@api_view(["GET"])
def ping(request):
    """DRF ping for versioned API root."""
    return Response(
        {"ok": True, "version": "v1", "debug": bool(getattr(settings, "DEBUG", False))}
    )


class ProviderViewSet(viewsets.ModelViewSet):
    """CRUD for Provider."""
    queryset = Provider.objects.all().order_by("id")
    serializer_class = ProviderSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "kind"]


class TokenViewSet(viewsets.ModelViewSet):
    """CRUD for Token with proper error handling."""
    queryset = Token.objects.all().order_by("id")
    serializer_class = TokenSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["symbol", "name", "address", "chain"]

    def create(self, request, *args, **kwargs):
        """Create token with proper validation and debugging."""
        try:
            print(f"Token creation request data: {request.data}")
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                headers = self.get_success_headers(serializer.data)
                print(f"Token created successfully: {serializer.data}")
                return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            else:
                print(f"Token creation validation failed: {serializer.errors}")
                return Response({
                    "error": "Invalid token data",
                    "details": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Token creation exception: {str(e)}")
            return Response({
                "error": f"Failed to create token: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        """Delete token with proper error handling for protected relationships."""
        try:
            instance = self.get_object()
            print(f"Attempting to delete token: {instance.symbol} (ID: {instance.id})")
            
            # Check if token is used in any pairs
            pair_count = instance.base_pairs.count() + instance.quote_pairs.count()
            print(f"Token {instance.symbol} is used in {pair_count} pairs")
            
            if pair_count > 0:
                error_msg = f"Cannot delete token '{instance.symbol}' because it is used in {pair_count} trading pair(s). Remove the pairs first."
                print(f"Token deletion blocked: {error_msg}")
                return Response({
                    "error": error_msg
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Safe to delete
            instance.delete()
            print(f"Token {instance.symbol} deleted successfully")
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except ProtectedError as e:
            error_msg = f"Cannot delete token because it is referenced by other records: {str(e)}"
            print(f"ProtectedError: {error_msg}")
            return Response({
                "error": error_msg
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            error_msg = f"Failed to delete token: {str(e)}"
            print(f"Delete exception: {error_msg}")
            return Response({
                "error": error_msg
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PairViewSet(viewsets.ModelViewSet):
    """CRUD for Pair."""
    queryset = Pair.objects.select_related("base_token", "quote_token").order_by("id")
    serializer_class = PairSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["address", "dex", "chain"]


class TradeViewSet(viewsets.ModelViewSet):
    """CRUD for Trade."""
    queryset = Trade.objects.select_related("pair").order_by("-created_at")
    serializer_class = TradeSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["tx_hash", "dex", "chain", "status", "side"]


class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/retrieve for ledger events."""
    queryset = LedgerEntry.objects.all().order_by("-timestamp")
    serializer_class = LedgerEntrySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["event_type", "tx_hash", "reason", "trace_id", "network", "dex"]


# Bot control endpoints
@api_view(["GET"])
@permission_classes([AllowAny])
def bot_status(request):
    """Get bot status - mock implementation."""
    return Response({
        "ok": True, 
        "status": "stopped",
        "uptime": 0,
        "last_trade": None
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def bot_start(request):
    """Start bot - mock implementation."""
    return Response({
        "ok": True, 
        "started": True, 
        "status": "running"
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def bot_stop(request):
    """Stop bot - mock implementation."""
    return Response({
        "ok": True, 
        "stopped": True, 
        "status": "stopped"
    })


@api_view(["GET", "PUT"])
@permission_classes([AllowAny])
def bot_settings(request):
    """Get/update bot settings - mock implementation."""
    if request.method == "GET":
        return Response({
            "max_slippage_bps": 300,
            "max_trade_size_eth": 1.0,
            "gas_price_multiplier": 1.2,
            "min_liquidity_usd": 10000.0,
        })
    else:
        # PUT - just return the data back for now
        return Response(request.data)


# CSV Export
def ledger_export_csv(request):
    """Export all LedgerEntry rows as CSV (UTC timestamps)."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ledger-{now().strftime("%Y%m%d-%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'id', 'timestamp_utc', 'event_type', 'network', 'dex', 
        'pair_address', 'tx_hash', 'amount_in', 'amount_out', 
        'fee_native', 'pnl_native', 'status', 'reason', 'trace_id', 'notes'
    ])
    
    for entry in LedgerEntry.objects.all().order_by('id'):
        writer.writerow([
            entry.id, entry.timestamp.isoformat(), entry.event_type,
            entry.network, entry.dex, entry.pair_address, entry.tx_hash,
            str(entry.amount_in), str(entry.amount_out), str(entry.fee_native),
            str(entry.pnl_native), entry.status, entry.reason, 
            entry.trace_id, entry.notes
        ])
    
    return response