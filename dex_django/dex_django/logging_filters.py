from __future__ import annotations

import re
import logging


class RedactSecretsFilter(logging.Filter):
    """
    Redacts obvious secrets (private keys, mnemonics, API tokens, JWTs) from log messages.
    Safe for general use; if formatting args were present, we reformat the message once and clear args.
    """

    # crude but effective patterns; expand later as needed
    PATTERNS = [
        re.compile(r"(?:0x)?[a-fA-F0-9]{64}"),                 # 64-hex (private keys)
        re.compile(r"\b(?:sk|pk|secret|token|apikey|api_key)\s*[:=]\s*[\w\-\.]{12,}", re.I),
        re.compile(r"\b[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b"),  # JWT
        re.compile(r"\b(?:seed|mnemonic)\s*[:=]\s*\"?[a-z ]{24,}\"?", re.I),
    ]

    REPLACEMENT = "[REDACTED]"

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            for pat in self.PATTERNS:
                msg = pat.sub(self.REPLACEMENT, msg)
            # ensure the redacted message is what gets output
            record.msg = msg
            record.args = ()
        except Exception:
            # never let logging crash the app
            pass
        return True
