from __future__ import annotations

import re
import time
import threading
from collections import deque

from config import (
    ANTI_SPAM_BURST_MESSAGES,
    ANTI_SPAM_BURST_WINDOW_SEC,
    ANTI_SPAM_NO_INTENT_TURNS,
    CONTACTS_RE,
    INPUT_MAX_CHARS,
    PRICE_CONCERN_RE,
    PRICE_LOOKUP_RE,
    RATE_LIMIT_MAX_PER_IP,
    RATE_LIMIT_WINDOW_SEC,
)
from contracts.ingress_route import IngressRouteResult
from core.client_config_loader import load_ui_bundle, ui_menu_to_payload
from dialog_offer import parse_lead_offer_no, parse_lead_offer_yes

_OBVIOUS_NOISE_RE = re.compile(r"^[^А-Яа-яЁёA-Za-z]{4,}$", re.U)
_REPEATED_CHAR_RE = re.compile(r"(.)\1{5,}", re.U)
_NEUTRAL_RX = re.compile(
    r"^(?:понятно|спасибо|хм+|ясно|окей|ок|ok|интересно|угу|ага|ладно|"
    r"хорошо|понял|поняла|ничего|неплохо|круто|отлично|супер)\W*$",
    re.I,
)

_IP_RATE_LOCK = threading.RLock()
_IP_RATE_BUCKETS: dict[str, deque] = {}


def normalize_question_text(text: str) -> tuple[str, bool]:
    q = (text or "").strip()
    if len(q) <= INPUT_MAX_CHARS:
        return q, False
    return q[:INPUT_MAX_CHARS], True


def resolve_client_ip(*, x_forwarded_for: str | None, remote_addr: str | None) -> str:
    xff = (x_forwarded_for or "").strip()
    if xff:
        return xff.split(",", 1)[0].strip() or (remote_addr or "unknown")
    return remote_addr or "unknown"


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    with _IP_RATE_LOCK:
        q = _IP_RATE_BUCKETS.get(ip)
        if q is None:
            q = deque()
            _IP_RATE_BUCKETS[ip] = q
        threshold = now - float(RATE_LIMIT_WINDOW_SEC)
        while q and q[0] < threshold:
            q.popleft()
        if len(q) >= int(RATE_LIMIT_MAX_PER_IP):
            return False
        q.append(now)
        return True


def rate_limited_response_payload() -> dict:
    return {
        "answer": "Слишком много запросов за короткое время. Подождите немного и попробуйте снова.",
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": {"error": "rate_limited"},
    }


def is_obvious_noise(q: str) -> bool:
    s = (q or "").strip()
    if not s:
        return False
    if len(s) <= 3 and not any(ch.isalpha() for ch in s):
        return True
    if _OBVIOUS_NOISE_RE.fullmatch(s):
        return True
    if _REPEATED_CHAR_RE.search(s):
        return True
    return False


def obvious_noise_ingress_result() -> IngressRouteResult:
    return IngressRouteResult(
        route="hard_stop_non_target",
        confidence=1.0,
        reason="obvious_noise",
        policy_key=None,
        requested_service=None,
        source="rule",
        is_urgent=False,
    )


def norm_dup_text(q: str) -> str:
    x = (q or "").strip().lower().replace("ё", "е")
    x = re.sub(r"[^\w\s]", " ", x, flags=re.U)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def is_duplicate_question(st: dict, q: str) -> bool:
    qn = norm_dup_text(q)
    if len(qn) < 5:
        return False
    hist = list((st or {}).get("hist") or [])
    last_users = [m.get("content", "") for m in hist if isinstance(m, dict) and m.get("role") == "user"]
    if not last_users:
        return False
    recent = last_users[-2:]
    return any(norm_dup_text(x) == qn for x in recent)


def duplicate_payload(sid: str, client_id: str | None, snap: dict | None) -> dict:
    quick = list((snap or {}).get("quick_replies") or [])
    cta = (snap or {}).get("cta")
    return {
        "answer": "Похоже, мы это уже обсудили чуть выше. Если хотите, могу продолжить по следующему шагу.",
        "quick_replies": quick[:2],
        "cta": cta if isinstance(cta, dict) else None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": {"sid": sid, "client_id": client_id, "duplicate_short_circuit": True},
    }


def should_soft_redirect_no_intent(st: dict) -> bool:
    turns = int((st or {}).get("session_turn_count") or 0)
    booking_ever = bool((st or {}).get("booking_intent_ever"))
    shown = bool((st or {}).get("anti_spam_redirect_shown"))
    return turns >= ANTI_SPAM_NO_INTENT_TURNS and (not booking_ever) and (not shown)


def is_message_burst(st: dict) -> bool:
    ts = list((st or {}).get("user_turn_timestamps") or [])
    if not ts:
        return False
    now = time.time()
    recent = [
        float(x)
        for x in ts
        if isinstance(x, (int, float)) and float(x) >= (now - ANTI_SPAM_BURST_WINDOW_SEC)
    ]
    return len(recent) >= ANTI_SPAM_BURST_MESSAGES


def soft_redirect_payload(sid: str, client_id: str | None) -> dict:
    ui = load_ui_bundle(client_id)
    payload = {
        "answer": ui.anti_spam_soft_redirect,
        "quick_replies": [],
        "cta": {"text": "Связаться с администратором", "action": "lead"},
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": {
            "sid": sid,
            "client_id": client_id,
            "anti_spam_soft_redirect": True,
        },
    }
    return payload


def continuation_clarify_payload(sid: str, client_id: str | None) -> dict:
    ui = load_ui_bundle(client_id)
    return ui_menu_to_payload(ui.continuation_clarify, sid=sid, client_id=client_id)


def is_short_contextual(q: str, st: dict | None) -> bool:
    """True если запрос короткий и без явного интента — нет смысла гнать в retrieval."""
    tokens = q.split()
    if len(tokens) > 3:
        return False
    if PRICE_LOOKUP_RE.search(q) or PRICE_CONCERN_RE.search(q) or CONTACTS_RE.search(q):
        return False
    if parse_lead_offer_yes(q) and not bool((st or {}).get("pending_lead_offer")):
        return True
    if parse_lead_offer_no(q) and not bool((st or {}).get("pending_lead_offer")):
        return True
    if _NEUTRAL_RX.search(q):
        return True
    return False
