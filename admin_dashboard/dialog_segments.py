"""Split one browser sid into admin 'visits' (dialogs) for dashboard UX."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

TurnRow = tuple[
    datetime,
    str | None,
    int,
    str | None,
    str | None,
    str | None,
    str | None,
    float,
]


def dialog_status(
    *,
    has_lead: bool,
    last_status: str | None,
    last_route: str | None,
) -> str:
    if has_lead:
        return "lead"
    if (last_status or "").lower() != "ok" or (last_route or "") in (
        "retrieval_no_candidates",
        "low_score_fallback",
    ):
        return "problem"
    return "ok"


def group_turns_into_visits(
    turns: list[TurnRow],
    lead_times: list[datetime],
    *,
    gap_minutes: int = 30,
) -> list[list[TurnRow]]:
    """New visit after idle gap, or once per lead before the next user turn."""
    if not turns:
        return []
    gap = max(1, int(gap_minutes))
    leads = sorted(lead_times)
    lead_idx = 0
    segments: list[list[TurnRow]] = [[turns[0]]]
    for i in range(1, len(turns)):
        prev = turns[i - 1]
        cur = turns[i]
        split = (cur[0] - prev[0]) >= timedelta(minutes=gap)
        if not split and lead_idx < len(leads):
            lt = leads[lead_idx]
            if lt <= prev[0] and cur[0] > lt:
                split = True
                lead_idx += 1
        if split:
            segments.append([cur])
        else:
            segments[-1].append(cur)
    return segments


def visit_has_lead(visit_turns: list[TurnRow], lead_times: list[datetime]) -> bool:
    if not visit_turns or not lead_times:
        return False
    start = visit_turns[0][0]
    end = visit_turns[-1][0]
    return any(start <= lt <= end for lt in lead_times)


def turn_row_to_dict(row: TurnRow) -> dict[str, Any]:
    ts, status, turn_number, user_text, bot_text, route, doc_id, latency_ms = row
    return {
        "ts": ts.isoformat() if ts else None,
        "turn_number": int(turn_number or 0),
        "user_text": user_text,
        "bot_text": bot_text,
        "route": route,
        "doc_id": doc_id,
        "status": status,
        "latency_ms": float(latency_ms or 0.0),
    }


def build_visit_item(
    sid: str,
    client_id: str,
    visit_index: int,
    visits_total: int,
    visit_turns: list[TurnRow],
    lead_times: list[datetime],
) -> dict[str, Any]:
    first = visit_turns[0]
    last = visit_turns[-1]
    has_lead = visit_has_lead(visit_turns, lead_times)
    last_route = last[5]
    last_status = last[1]
    return {
        "sid": sid,
        "visit_index": visit_index,
        "visits_total": visits_total,
        "client_id": client_id,
        "last_ts": last[0].isoformat() if last[0] else None,
        "turns": len(visit_turns),
        "turn_number": int(last[2] or 0),
        "last_route": last_route,
        "first_user_text": first[3] or "",
        "last_user_text": last[3] or "",
        "last_bot_text": last[4] or "",
        "last_status": last_status,
        "has_lead": has_lead,
        "status": dialog_status(has_lead=has_lead, last_status=last_status, last_route=last_route),
    }
