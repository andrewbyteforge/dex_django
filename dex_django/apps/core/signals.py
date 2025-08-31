from __future__ import annotations

import logging
from django.db.backends.signals import connection_created

logger = logging.getLogger(__name__)


def apply_sqlite_pragmas(sender, connection, **kwargs) -> None:
    """
    Set SQLite pragmas on first real DB connection.
    Safe no-op for non-SQLite backends.
    """
    try:
        if connection.vendor != "sqlite":
            return

        with connection.cursor() as cur:
            cur.execute("PRAGMA journal_mode=WAL;")
            try:
                cur.fetchone()  # drain if driver returns a row
            except Exception:
                pass
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA foreign_keys=ON;")

        logger.info("SQLite pragmas applied via connection_created signal.")
    except Exception:  # pragma: no cover
        logger.exception("Failed to apply SQLite pragmas via signal.")
