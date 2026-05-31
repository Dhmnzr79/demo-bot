from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flask import request

from core.routing_loader import THRESHOLDS
from llm import classify_intent
from logging_setup import emit_bot_event, get_logger, log_json
from resolver import maybe_start_shadow_resolver, resolve_with_fallback

logger = get_logger("bot")


@dataclass(frozen=True)
class ResolverTurnOutcome:
    intent: str
    decision: Any
    scope_topic_candidate: str | None
    resolver_bypassed_env: bool


def is_resolver_bypassed_env() -> bool:
    """PR #1.2: emergency v4 path — only exact ``RESOLVER_OFF=1``."""
    return os.environ.get("RESOLVER_OFF") == "1"


def run_resolver_turn(
    *,
    q: str,
    sid: str,
    client_id: str,
    st: dict,
    enqueue_resolver_trace: Callable[..., None],
) -> ResolverTurnOutcome:
    """
    Resolver path; legacy classify_intent only on RESOLVER_OFF=1 or safety-net (inside resolver).
    Phase 3: removed parallel classify_intent on every turn (telemetry-only duplicate LLM call).
    """
    resolver_bypassed_env = is_resolver_bypassed_env()
    safety_net_used: list[str] = []
    decision = None
    intent: str

    if resolver_bypassed_env:
        log_json(logger, "resolver_bypassed_env", sid=sid, client_id=client_id)
        intent = classify_intent(q, client_id=client_id, sid=sid)
        request.ctx["legacy_intent"] = intent
        request.ctx["effective_intent"] = str(intent)
        request.ctx["resolver_used"] = False
        request.ctx["safety_net_used"] = False
        maybe_start_shadow_resolver(question=q, sid=sid, client_id=client_id)
        enqueue_resolver_trace(
            decision=None, safety_net_used=[], resolver_bypassed_env=True
        )
    else:
        hist = list((st or {}).get("hist") or [])
        decision, safety_net_used, legacy_intent = resolve_with_fallback(
            question=q,
            history=hist,
            client_id=client_id,
            sid=sid,
            session_state=st,
        )
        request.ctx["legacy_intent"] = legacy_intent
        request.ctx["resolver_used"] = True
        request.ctx["safety_net_used"] = bool(safety_net_used)
        emit_bot_event(
            logger,
            "v5_decision_frame_used",
            status="ok",
            details={
                "decision_frame": decision.model_dump(),
                "safety_net_used": safety_net_used,
                "resolver_bypassed_env": False,
            },
        )
        enqueue_resolver_trace(
            decision=decision,
            safety_net_used=safety_net_used,
            resolver_bypassed_env=False,
        )
        ri = str(decision.route_intent or "").strip().lower()
        if ri in ("price_lookup", "price_concern"):
            intent = ri
        else:
            intent = "content"
        request.ctx["effective_intent"] = str(intent)

    scope_topic_candidate: str | None = None
    if decision is not None:
        st_tp = decision.service_topic
        if (
            st_tp
            and str(st_tp).strip().lower() not in ("", "unknown")
            and float(decision.confidence.topic or 0.0)
            >= float(THRESHOLDS.retrieval.scope_topic_min_confidence)
        ):
            scope_topic_candidate = str(st_tp).strip().lower()
        qm_rs = str(decision.query_mode or "").strip().lower()
        if qm_rs in ("comparison", "process") and scope_topic_candidate is not None:
            scope_topic_candidate = None

    return ResolverTurnOutcome(
        intent=intent,
        decision=decision,
        scope_topic_candidate=scope_topic_candidate,
        resolver_bypassed_env=resolver_bypassed_env,
    )
