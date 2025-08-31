from __future__ import annotations

import threading
import time
import logging
from dataclasses import dataclass
from typing import Optional

from django.utils import timezone
from apps.strategy.models import BotSettings

logger = logging.getLogger("api")


@dataclass
class RunnerState:
    running: bool = False
    started_at: Optional[str] = None
    last_beat: Optional[str] = None
    loop_count: int = 0


class BotRunner:
    """
    Minimal, safe, single-process runner controlled via API.
    Thread stops via Event; no busy-wait; logs heartbeats.
    """
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.state = RunnerState()

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="bot-runner", daemon=True)
            self._thread.start()
            self.state.running = True
            self.state.started_at = timezone.now().isoformat()
            logger.info("BotRunner started")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not (self._thread and self._thread.is_alive()):
                return False
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        with self._lock:
            self.state.running = False
            logger.info("BotRunner stopped")
            return True

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self.state.running,
                "started_at": self.state.started_at,
                "last_beat": self.state.last_beat,
                "loop_count": self.state.loop_count,
            }

    def _loop(self) -> None:
        # very small heartbeat loop reading BotSettings
        while not self._stop.is_set():
            try:
                bs = BotSettings.objects.first()
                if not bs:
                    bs = BotSettings.objects.create()
                # here we would branch by settings (mainnet/autotrade/etc.)
                # for now, just heartbeat:
                with self._lock:
                    self.state.loop_count += 1
                    self.state.last_beat = timezone.now().isoformat()
                logger.info("Bot heartbeat #%s base=%s autotrade=%s mainnet=%s",
                            self.state.loop_count, bs.base_currency, bs.autotrade_enabled, bs.mainnet_enabled)
            except Exception:
                logger.exception("Bot loop error")
            # 1s sleep with cooperative stop
            self._stop.wait(1.0)


# process-wide singleton
runner = BotRunner()
