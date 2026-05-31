from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AskTurnContext:
    """Состояние turn после pre-Resolver guards — готов к Resolver + post-Resolver routing."""

    q: str
    sid: str
    client_id: str
    ref: str
    data: dict
    st: dict
