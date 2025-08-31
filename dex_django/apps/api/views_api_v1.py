from __future__ import annotations

from rest_framework import viewsets, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings

from apps.storage.models import Provider, Token, Pair, Trade
from .serializers import (
    ProviderSerializer,
    TokenSerializer,
    PairSerializer,
    TradeSerializer,
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
    """CRUD for Token."""
    queryset = Token.objects.all().order_by("id")
    serializer_class = TokenSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["symbol", "name", "address", "chain"]


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


from apps.storage.models import Provider, Token, Pair, Trade, LedgerEntry  # add LedgerEntry
from .serializers import (  # add LedgerEntrySerializer
    ProviderSerializer,
    TokenSerializer,
    PairSerializer,
    TradeSerializer,
    LedgerEntrySerializer,
)

from rest_framework import viewsets, filters  # keep existing import

class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/retrieve for ledger events."""
    queryset = LedgerEntry.objects.all().order_by("-timestamp")
    serializer_class = LedgerEntrySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["event_type", "tx_hash", "reason", "trace_id", "network", "dex"]


# extend existing imports
from apps.storage.models import Provider, Token, Pair, Trade, LedgerEntry
from .serializers import (
    ProviderSerializer,
    TokenSerializer,
    PairSerializer,
    TradeSerializer,
    LedgerEntrySerializer,  # add
)



import csv
from django.http import HttpResponse
from django.utils.timezone import now
from apps.storage.models import LedgerEntry

# ...

def ledger_export_csv(request):
    """
    Export all LedgerEntry rows as CSV (UTC timestamps).
    Route: /api/v1/ledger/export.csv
    """
    ts = now().strftime("%Y%m%d-%H%M%S")
    filename = f"ledger-{ts}.csv"
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    headers = [
        "id",
        "timestamp_utc",
        "event_type",
        "network",
        "dex",
        "pair_address",
        "tx_hash",
        "amount_in",
        "amount_out",
        "fee_native",
        "pnl_native",
        "status",
        "reason",
        "trace_id",
        "notes",
    ]
    writer.writerow(headers)

    qs = LedgerEntry.objects.all().order_by("id").iterator(chunk_size=1000)
    for row in qs:
        writer.writerow(
            [
                row.id,
                row.timestamp.isoformat(),
                row.event_type,
                row.network,
                row.dex,
                row.pair_address,
                row.tx_hash,
                row.amount_in,
                row.amount_out,
                row.fee_native,
                row.pnl_native,
                row.status,
                row.reason,
                row.trace_id,
                row.notes,
            ]
        )

    return response



from io import BytesIO
from django.http import HttpResponse

def ledger_export_xlsx(request):
    """
    Export all LedgerEntry rows as an .xlsx file.
    Route: /api/v1/ledger/export.xlsx
    """
    # Lazy import so we don’t require openpyxl during startup
    from openpyxl import Workbook
    from django.utils.timezone import now
    from apps.storage.models import LedgerEntry

    wb = Workbook()
    ws = wb.active
    ws.title = "ledger"

    headers = [
        "id",
        "timestamp_utc",
        "event_type",
        "network",
        "dex",
        "pair_address",
        "tx_hash",
        "amount_in",
        "amount_out",
        "fee_native",
        "pnl_native",
        "status",
        "reason",
        "trace_id",
        "notes",
    ]
    ws.append(headers)

    for row in LedgerEntry.objects.all().order_by("id").iterator(chunk_size=1000):
        ws.append(
            [
                row.id,
                row.timestamp.isoformat(),
                row.event_type,
                row.network,
                row.dex,
                row.pair_address,
                row.tx_hash,
                str(row.amount_in),
                str(row.amount_out),
                str(row.fee_native),
                str(row.pnl_native),
                row.status,
                row.reason,
                row.trace_id,
                row.notes,
            ]
        )

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    ts = now().strftime("%Y%m%d-%H%M%S")
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="ledger-{ts}.xlsx"'
    return resp



# at top with other imports
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as drf_status

from apps.strategy.models import BotSettings
from .serializers import BotSettingsSerializer
from apps.strategy.runner import runner

@api_view(["GET", "PUT"])
@permission_classes([AllowAny])
def bot_settings(request):
    obj = BotSettings.objects.first() or BotSettings.objects.create()
    if request.method == "GET":
        return Response(BotSettingsSerializer(obj).data)
    # PUT
    ser = BotSettingsSerializer(obj, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response(ser.data)

@api_view(["GET"])
@permission_classes([AllowAny])
def bot_status(request):
    return Response({"ok": True, "status": runner.status()})

@api_view(["POST"])
@permission_classes([AllowAny])
def bot_start(request):
    started = runner.start()
    return Response({"ok": True, "started": started, "status": runner.status()},
                    status=drf_status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([AllowAny])
def bot_stop(request):
    stopped = runner.stop()
    return Response({"ok": True, "stopped": stopped, "status": runner.status()},
                    status=drf_status.HTTP_200_OK)
