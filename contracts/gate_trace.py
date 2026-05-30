from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GateSource = Literal["regex", "rule", "catalog", "llm"]


class GateTrace(BaseModel):
    """Hard gate output contract. See `contracts/` and `docs/CURRENT_ARCHITECTURE.md`."""

    model_config = ConfigDict(extra="forbid")

    gate: str = Field(..., min_length=1)
    passed: bool
    route: str | None = None
    payload: dict[str, Any] | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: GateSource
    reason: str

