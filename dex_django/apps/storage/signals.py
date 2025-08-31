from __future__ import annotations

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Trade, LedgerEntry

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Trade, dispatch_uid="trade_to_ledger_v1")
def trade_to_ledger(sender, instance: Trade, created: bool, **kwargs) -> None:
    """
    Mirror Trade rows into LedgerEntry for audit/export.
    """
    try:
        LedgerEntry.objects.create(
            event_type="buy" if instance.side == Trade.Side.BUY else "sell",
            network=instance.chain,
            dex=instance.dex,
            pair_address=instance.pair.address if instance.pair_id else "",
            tx_hash=instance.tx_hash,
            amount_in=instance.amount_in,
            amount_out=instance.amount_out,
            fee_native=instance.gas_native,
            pnl_native=0,  # computed later
            status="ok" if instance.status == "filled" else "fail",
            reason=instance.reason,
            trace_id="",
            notes="auto: trade created" if created else "auto: trade updated",
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to create LedgerEntry for Trade id=%s", instance.id)
