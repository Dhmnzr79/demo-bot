from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArbiterDecision(BaseModel):
    """Arbiter output contract. See `contracts/` and `docs/CURRENT_ARCHITECTURE.md`."""

    model_config = ConfigDict(extra="forbid")

    selected_ref: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    alternative: str | None = None

