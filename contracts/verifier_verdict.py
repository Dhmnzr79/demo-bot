from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VerifierVerdict(BaseModel):
    """Verifier output contract. See `contracts/` and `docs/CURRENT_ARCHITECTURE.md`."""

    model_config = ConfigDict(extra="forbid")

    grounded: bool
    hallucinated_facts: list[str]
    confidence: float = Field(..., ge=0.0, le=1.0)

