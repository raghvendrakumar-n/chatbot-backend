"""Intent detection — re-exports from ``flows`` for backward compatibility."""
from __future__ import annotations

from .flows import INTENTS, detect_intent

__all__ = ["INTENTS", "detect_intent"]
