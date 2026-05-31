"""Internal dashboard service (read-only) for bot analytics."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from flask import Flask, jsonify, render_template, request

from core.client_config_loader import admin_client_options, list_admin_client_ids
from admin_dashboard.dialog_segments import (
    TurnRow,
    build_visit_item,
    dialog_status,
    group_turns_into_visits,
    turn_row_to_dict,
    visit_has_lead,
)

try:
    import psycopg
except Exception:  # pragma: no cover - runtime guard
    psycopg = None


APP_ENV = (os.getenv("APP_ENV") or "local").strip().lower()
BOT_PG_DSN = (os.getenv("BOT_PG_DSN") or "").strip()
PORT = int(os.getenv("ADMIN_DASHBOARD_PORT", "9100"))
ADMIN_TOKEN = (os.getenv("ADMIN_DASHBOARD_TOKEN") or "").strip()
DB_CONNECT_TIMEOUT_SEC = int(os.getenv("ADMIN_DASHBOARD_DB_CONNECT_TIMEOUT_SEC", "3"))
VISIT_GAP_MINUTES = int(os.getenv("ADMIN_DIALOG_VISIT_GAP_MIN", "30"))

_DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_DASHBOARD_DIR, "templates"),
    static_folder=os.path.join(_DASHBOARD_DIR, "static"),
)
if APP_ENV == "local":
    app.config["TEMPLATES_AUTO_RELOAD"] = True
_SCHEMA_ENSURED = False


def _utc_day_bounds(days_back: int = 0) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    d0 = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=days_back)
    d1 = d0 + timedelta(days=1)
    return d0, d1


def _guard():
    # Local mode: no token by default.
    if APP_ENV != "prod":
        return None
    expected = ADMIN_TOKEN
    if not expected:
        return jsonify({"error": "dashboard_token_not_set"}), 503
    got = (request.headers.get("X-Admin-Dashboard-Token") or "").strip()
    if got == expected:
        return None
    return jsonify({"error": "not_found"}), 404


def _require_db():
    global _SCHEMA_ENSURED
    if not BOT_PG_DSN:
        return None, (jsonify({"error": "BOT_PG_DSN_not_set"}), 503)
    if psycopg is None:
        return None, (jsonify({"error": "psycopg_not_installed"}), 503)
    try:
        conn = psycopg.connect(BOT_PG_DSN, autocommit=True, connect_timeout=max(1, DB_CONNECT_TIMEOUT_SEC))
        if not _SCHEMA_ENSURED:
            from pg_sink import ensure_pg_schema_conn

            ensure_pg_schema_conn(conn)
            _SCHEMA_ENSURED = True
    except Exception as e:
        return None, (jsonify({"error": "db_connect_failed", "details": str(e)[:200]}), 503)
    return conn, None


def _default_client_id() -> str:
    ids = list_admin_client_ids()
    return ids[0] if ids else "cesi"


def _client_id() -> str:
    raw = (request.args.get("client_id") or "").strip()
    return _resolve_client_id(raw if raw else None)


def _resolve_client_id(raw: str | None) -> str:
    cid = (raw or "").strip()
    if cid:
        allowed = {item["client_id"] for item in admin_client_options()}
        if cid in allowed:
            return cid
    return _default_client_id()


def _to_int(value: str | None, default: int, min_v: int, max_v: int) -> int:
    try:
        v = int(value or default)
    except Exception:
        v = default
    return min(max(v, min_v), max_v)


def _dialog_status(
    *,
    has_lead: bool,
    last_status: str | None,
    last_route: str | None,
) -> str:
    return dialog_status(has_lead=has_lead, last_status=last_status, last_route=last_route)


def _fetch_turn_rows(
    cur,
    cid: str,
    *,
    sid: str | None = None,
    d0: datetime | None = None,
    d1: datetime | None = None,
) -> dict[str, list[TurnRow]]:
    where = ["client_id=%s", "event_type='turn_complete'", "sid IS NOT NULL"]
    params: list[object] = [cid]
    if sid:
        where.append("sid=%s")
        params.append(sid)
    if d0 is not None:
        where.append("occurred_at >= %s")
        params.append(d0)
    if d1 is not None:
        where.append("occurred_at < %s")
        params.append(d1)
    cur.execute(
        f"""
        SELECT
          sid,
          occurred_at,
          status,
          COALESCE((details->>'turn_number')::int, 0) AS turn_number,
          COALESCE(
            NULLIF(details->>'user_text_redacted', ''),
            details->>'user_preview_redacted'
          ) AS user_text,
          details->>'bot_text_redacted' AS bot_text,
          details->>'route' AS route,
          COALESCE(details->>'doc_id', details->>'chunk_id') AS doc_id,
          COALESCE((details->>'latency_ms')::numeric, 0)::float AS latency_ms
        FROM bot_events
        WHERE {' AND '.join(where)}
        ORDER BY sid, occurred_at ASC
        """,
        tuple(params),
    )
    by_sid: dict[str, list[TurnRow]] = {}
    for sid_val, ts, status, turn_number, user_text, bot_text, route, doc_id, latency_ms in cur.fetchall():
        by_sid.setdefault(str(sid_val), []).append(
            (ts, status, int(turn_number or 0), user_text, bot_text, route, doc_id, float(latency_ms or 0.0))
        )
    return by_sid


def _fetch_lead_times(cur, cid: str, *, d0: datetime | None = None, d1: datetime | None = None) -> dict[str, list[datetime]]:
    where = ["client_id=%s", "event_type='lead_submitted'", "status='ok'", "sid IS NOT NULL"]
    params: list[object] = [cid]
    if d0 is not None:
        where.append("occurred_at >= %s")
        params.append(d0)
    if d1 is not None:
        where.append("occurred_at < %s")
        params.append(d1)
    cur.execute(
        f"""
        SELECT sid, occurred_at
        FROM bot_events
        WHERE {' AND '.join(where)}
        ORDER BY sid, occurred_at ASC
        """,
        tuple(params),
    )
    out: dict[str, list[datetime]] = {}
    for sid_val, ts in cur.fetchall():
        out.setdefault(str(sid_val), []).append(ts)
    return out


def _build_visit_list(
    turns_by_sid: dict[str, list[TurnRow]],
    leads_by_sid: dict[str, list[datetime]],
    *,
    client_id: str,
    limit: int,
) -> list[dict]:
    items: list[dict] = []
    for sid, turns in turns_by_sid.items():
        if not turns:
            continue
        visits = group_turns_into_visits(
            turns,
            leads_by_sid.get(sid, []),
            gap_minutes=VISIT_GAP_MINUTES,
        )
        total = len(visits)
        for idx, visit_turns in enumerate(visits):
            items.append(
                build_visit_item(sid, client_id, idx, total, visit_turns, leads_by_sid.get(sid, []))
            )
    items.sort(key=lambda x: x.get("last_ts") or "", reverse=True)
    return items[:limit]


@app.get("/")
def home():
    denied = _guard()
    if denied:
        return denied
    default_client_id = _default_client_id()
    return render_template(
        "index.html",
        app_env=APP_ENV,
        default_client_id=default_client_id,
    )


@app.get("/api/health")
def api_health():
    denied = _guard()
    if denied:
        return denied
    if not BOT_PG_DSN:
        return jsonify({"ok": False, "postgres": "BOT_PG_DSN_not_set", "app_env": APP_ENV}), 503
    if psycopg is None:
        return jsonify({"ok": False, "postgres": "psycopg_not_installed", "app_env": APP_ENV}), 503
    conn, err = _require_db()
    if err:
        body = err[0].get_json(silent=True) or {}
        return jsonify({"ok": False, "postgres": body.get("error", "db_connect_failed"), "app_env": APP_ENV}), 503
    conn.close()
    return jsonify({"ok": True, "postgres": "connected", "app_env": APP_ENV})


@app.get("/api/clients")
def api_clients():
    denied = _guard()
    if denied:
        return denied
    items = admin_client_options()
    return jsonify({"items": items, "default_client_id": _default_client_id()})


@app.get("/api/overview")
def api_overview():
    denied = _guard()
    if denied:
        return denied
    conn, err = _require_db()
    if err:
        return err
    cid = _client_id()
    d0, d1 = _utc_day_bounds(0)
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  count(*) FILTER (WHERE event_type='user_turn_completed') AS user_turns,
                  count(DISTINCT sid) FILTER (WHERE sid IS NOT NULL) AS sessions,
                  count(DISTINCT sid) FILTER (
                    WHERE sid IS NOT NULL AND event_type='lead_submitted' AND status='ok'
                  ) AS sessions_with_lead,
                  count(*) FILTER (WHERE event_type='lead_submitted' AND status='ok') AS leads,
                  count(*) FILTER (WHERE event_type='llm_error') AS llm_errors,
                  count(*) FILTER (WHERE status='error' OR event_type IN ('llm_error', 'ask_failed', 'ask_stream_failed')) AS errors,
                  count(*) FILTER (WHERE event_type='turn_complete' AND details->>'route'='retrieval_no_candidates') AS no_candidates,
                  count(*) FILTER (WHERE event_type='turn_complete' AND details->>'route'='low_score_fallback') AS low_score_fallback,
                  COALESCE(avg((details->>'latency_ms')::numeric) FILTER (WHERE event_type='turn_complete' AND details ? 'latency_ms'), 0)::float AS avg_latency_ms
                FROM bot_events
                WHERE client_id = %s AND occurred_at >= %s AND occurred_at < %s
                """,
                (cid, d0, d1),
            )
            row = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0, 0, 0)
            turns_today = _fetch_turn_rows(cur, cid, d0=d0, d1=d1)
            leads_today = _fetch_lead_times(cur, cid, d0=d0, d1=d1)
            visits_today = _build_visit_list(turns_today, leads_today, client_id=cid, limit=10_000)
            cur.execute(
                """
                SELECT
                  COALESCE(sum((details->>'estimated_usd')::numeric), 0)::float
                FROM bot_events
                WHERE client_id=%s
                  AND event_type='llm_usage'
                  AND occurred_at >= %s AND occurred_at < %s
                """,
                (cid, d0, d1),
            )
            usd = float((cur.fetchone() or [0.0])[0] or 0.0)
    sessions = int(row[1] or 0)
    sessions_with_lead = int(row[2] or 0)
    leads = int(row[3] or 0)
    visits = len(visits_today)
    return jsonify(
        {
            "client_id": cid,
            "today_utc": d0.date().isoformat(),
            "user_turns": int(row[0] or 0),
            "visits": visits,
            "conversations": visits,
            "sessions": sessions,
            "sessions_with_lead": sessions_with_lead,
            "leads": leads,
            "llm_errors": int(row[4] or 0),
            "errors": int(row[5] or 0),
            "no_candidates": int(row[6] or 0),
            "low_score_fallback": int(row[7] or 0),
            "fallbacks_total": int((row[6] or 0) + (row[7] or 0)),
            "avg_latency_ms": float(row[8] or 0.0),
            "estimated_usd": round(usd, 6),
            "conversion_percent": round(((sessions_with_lead / max(sessions, 1)) * 100.0), 2),
        }
    )


@app.get("/api/dialogs")
def api_dialogs():
    denied = _guard()
    if denied:
        return denied
    conn, err = _require_db()
    if err:
        return err
    cid = _client_id()
    limit = _to_int(request.args.get("limit"), 30, 1, 200)
    with conn:
        with conn.cursor() as cur:
            turns_by_sid = _fetch_turn_rows(cur, cid)
            leads_by_sid = _fetch_lead_times(cur, cid)
    out = _build_visit_list(turns_by_sid, leads_by_sid, client_id=cid, limit=limit)
    return jsonify({"client_id": cid, "items": out})


@app.get("/api/dialogs/<sid>/thread")
def api_dialog_thread(sid: str):
    denied = _guard()
    if denied:
        return denied
    conn, err = _require_db()
    if err:
        return err
    cid = _client_id()
    sid_clean = (sid or "").strip()
    if not sid_clean:
        return jsonify({"error": "sid_required"}), 400
    visit_index = _to_int(request.args.get("visit_index"), 0, 0, 999)
    with conn:
        with conn.cursor() as cur:
            turns_by_sid = _fetch_turn_rows(cur, cid, sid=sid_clean)
            leads_by_sid = _fetch_lead_times(cur, cid)
    turns = turns_by_sid.get(sid_clean, [])
    if not turns:
        return jsonify({"error": "not_found", "sid": sid_clean, "client_id": cid}), 404
    visits = group_turns_into_visits(
        turns,
        leads_by_sid.get(sid_clean, []),
        gap_minutes=VISIT_GAP_MINUTES,
    )
    if visit_index >= len(visits):
        return jsonify({"error": "visit_not_found", "sid": sid_clean, "visit_index": visit_index}), 404
    visit_turns = visits[visit_index]
    last = visit_turns[-1]
    has_lead = visit_has_lead(visit_turns, leads_by_sid.get(sid_clean, []))
    return jsonify(
        {
            "client_id": cid,
            "sid": sid_clean,
            "visit_index": visit_index,
            "visits_total": len(visits),
            "turns": [turn_row_to_dict(row) for row in visit_turns],
            "turns_count": len(visit_turns),
            "has_lead": has_lead,
            "status": _dialog_status(has_lead=has_lead, last_status=last[1], last_route=last[5]),
        }
    )


@app.get("/api/problems")
def api_problems():
    denied = _guard()
    if denied:
        return denied
    conn, err = _require_db()
    if err:
        return err
    cid = _client_id()
    limit = _to_int(request.args.get("limit"), 50, 1, 300)
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH bad_events AS (
                  SELECT
                    occurred_at AS ts,
                    sid,
                    event_type,
                    COALESCE(details->>'user_text_redacted', details->>'user_preview_redacted') AS user_text,
                    COALESCE(details->>'route', '') AS route,
                    COALESCE(details->>'error', details->>'fallback_reason', status, event_type) AS reason,
                    COALESCE(details->>'doc_id', details->>'chunk_id') AS doc_id,
                    CASE
                      WHEN event_type IN ('llm_error', 'ask_failed', 'ask_stream_failed') OR status='error' THEN 'high'
                      WHEN details->>'route'='retrieval_no_candidates' THEN 'high'
                      WHEN details->>'route'='low_score_fallback' THEN 'medium'
                      ELSE 'low'
                    END AS priority
                  FROM bot_events
                  WHERE client_id=%s
                    AND (
                      status='error'
                      OR event_type IN ('llm_error', 'ask_failed', 'ask_stream_failed')
                      OR (event_type='turn_complete' AND details->>'route' IN ('retrieval_no_candidates', 'low_score_fallback'))
                    )
                ),
                bad_leads AS (
                  SELECT
                    captured_at AS ts,
                    sid,
                    'lead_delivery_issue' AS event_type,
                    NULL::text AS user_text,
                    NULL::text AS route,
                    COALESCE(delivery_status, 'unknown') AS reason,
                    NULL::text AS doc_id,
                    'medium'::text AS priority
                  FROM leads
                  WHERE client_id=%s
                    AND COALESCE(delivery_status, '') <> 'email'
                )
                SELECT ts, sid, event_type, user_text, route, reason, doc_id, priority
                FROM (
                  SELECT * FROM bad_events
                  UNION ALL
                  SELECT * FROM bad_leads
                ) p
                ORDER BY ts DESC
                LIMIT %s
                """,
                (cid, cid, limit),
            )
            rows = cur.fetchall()
    items = []
    for ts, sid, event_type, user_text, route, reason, doc_id, priority in rows:
        items.append(
            {
                "ts": ts.isoformat(),
                "sid": sid,
                "event_type": event_type,
                "user_text": user_text,
                "route": route,
                "reason": reason,
                "doc_id": doc_id,
                "priority": priority,
            }
        )
    return jsonify({"client_id": cid, "items": items})


@app.get("/api/leads")
def api_leads():
    denied = _guard()
    if denied:
        return denied
    conn, err = _require_db()
    if err:
        return err
    cid = _client_id()
    limit = min(max(int(request.args.get("limit", 50)), 1), 300)
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT captured_at, request_id, sid, name, phone, topic, cta_action, turns_to_lead, delivery_status
                FROM leads
                WHERE client_id=%s
                ORDER BY captured_at DESC
                LIMIT %s
                """,
                (cid, limit),
            )
            rows = cur.fetchall()
    items = []
    for ts, request_id, sid, name, phone, topic, cta_action, turns_to_lead, delivery_status in rows:
        items.append(
            {
                "captured_at": ts.isoformat() if ts else None,
                "request_id": request_id,
                "sid": sid,
                "name": name,
                "phone": phone,
                "topic": topic,
                "cta_action": cta_action,
                "turns_to_lead": turns_to_lead,
                "delivery_status": delivery_status,
                "client_id": cid,
            }
        )
    return jsonify({"client_id": cid, "items": items})


@app.get("/api/costs")
def api_costs():
    denied = _guard()
    if denied:
        return denied
    conn, err = _require_db()
    if err:
        return err
    cid = _client_id()
    d0, d1 = _utc_day_bounds(0)
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  details->>'call_type' AS call_type,
                  count(*) AS calls,
                  COALESCE(sum((details->>'prompt_tokens')::numeric),0)::bigint AS prompt_tokens,
                  COALESCE(sum((details->>'completion_tokens')::numeric),0)::bigint AS completion_tokens,
                  COALESCE(sum((details->>'estimated_usd')::numeric),0)::float AS usd
                FROM bot_events
                WHERE client_id=%s AND event_type='llm_usage'
                  AND occurred_at >= %s AND occurred_at < %s
                GROUP BY details->>'call_type'
                ORDER BY usd DESC, calls DESC
                """,
                (cid, d0, d1),
            )
            rows = cur.fetchall()
    items = []
    total = 0.0
    for call_type, calls, pt, ct, usd in rows:
        val = float(usd or 0.0)
        total += val
        items.append(
            {
                "call_type": call_type or "unknown",
                "calls": int(calls or 0),
                "prompt_tokens": int(pt or 0),
                "completion_tokens": int(ct or 0),
                "estimated_usd": round(val, 6),
            }
        )
    return jsonify({"client_id": cid, "today_utc": d0.date().isoformat(), "estimated_usd_total": round(total, 6), "items": items})


@app.get("/api/events")
def api_events():
    denied = _guard()
    if denied:
        return denied
    conn, err = _require_db()
    if err:
        return err
    cid = _client_id()
    limit = _to_int(request.args.get("limit"), 200, 1, 1000)
    event_type = (request.args.get("event_type") or "").strip()
    sid = (request.args.get("sid") or "").strip()
    request_id = (request.args.get("request_id") or "").strip()
    with conn:
        with conn.cursor() as cur:
            where_parts = ["client_id=%s"]
            params: list[object] = [cid]
            if event_type:
                where_parts.append("event_type=%s")
                params.append(event_type)
            if sid:
                where_parts.append("sid=%s")
                params.append(sid)
            if request_id:
                where_parts.append("request_id=%s")
                params.append(request_id)
            params.append(limit)
            query = f"""
                SELECT occurred_at, event_type, request_id, sid, status, details
                FROM bot_events
                WHERE {' AND '.join(where_parts)}
                ORDER BY occurred_at DESC
                LIMIT %s
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
    items = []
    for ts, event_type, request_id, sid, status, details in rows:
        items.append(
            {
                "ts": ts.isoformat(),
                "event_type": event_type,
                "request_id": request_id,
                "sid": sid,
                "status": status,
                "details": details or {},
            }
        )
    return jsonify({"client_id": cid, "items": items})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

