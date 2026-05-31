"""Load client pack configs: features, tone, ui, lead, widget (M3)."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any

import yaml

from config import DEFAULT_CLIENT_ID

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOCK = threading.Lock()
_FEATURES_CACHE: dict[str, dict[str, Any]] = {}
_TONE_CACHE: dict[str, dict[str, Any]] = {}
_UI_CACHE: dict[str, dict[str, Any]] = {}
_LEAD_CACHE: dict[str, dict[str, Any]] = {}
_TXT_CACHE: dict[str, dict[str, str]] = {}

# Legacy flat keys used by flow_handlers / app (from tone.yaml).
_TONE_KEY_MAP: tuple[tuple[str, str], ...] = (
    (("lead", "name_prompt"), "lead_name_prompt"),
    (("lead", "name_retry"), "lead_name_retry"),
    (("lead", "name_hard"), "lead_name_hard"),
    (("lead", "name_invalid"), "lead_name_invalid"),
    (("lead", "name_confirm_tpl"), "lead_name_confirm_tpl"),
    (("lead", "name_reenter"), "lead_name_reenter"),
    (("lead", "phone_prompt_tpl"), "lead_phone_prompt_tpl"),
    (("lead", "phone_retry"), "lead_phone_retry"),
    (("lead", "submit_ok"), "lead_submit_ok"),
    (("lead", "submit_ok_after_hours"), "lead_submit_ok_after_hours"),
    (("lead", "submit_error"), "lead_submit_error"),
    (("lead", "offer_declined"), "lead_offer_declined"),
    (("situation", "prompt"), "situation_prompt"),
    (("situation", "retry_short"), "situation_retry_short"),
    (("situation", "to_lead_name"), "situation_to_lead_name"),
    (("situation", "back_fallback"), "situation_back_fallback"),
    (("guided_menu", "answer"), "guided_menu_answer"),
    (("continuation", "clarify_answer"), "continuation_clarify_answer"),
    (("fallback", "bare_affirmative"), "bare_affirmative_fallback"),
    (("followup", "choose_topic"), "followup_choose_topic"),
)

_FALLBACK_TXT: dict[str, str] = {
    "lead_name_prompt": "Хорошо, помогу с записью. Как к вам можно обращаться?",
    "lead_name_retry": "Как к вам можно обращаться? Напишите, пожалуйста, имя.",
    "lead_name_hard": "Напишите просто имя — например, Мария или Андрей.",
    "lead_name_invalid": "Не совсем поняла — напишите просто имя, например Мария.",
    "lead_name_confirm_tpl": "Вас зовут {name}, правильно?",
    "lead_name_reenter": "Хорошо. Как к вам можно обращаться?",
    "lead_phone_prompt_tpl": (
        "{name}, оставьте, пожалуйста, номер телефона — администратор свяжется с вами, "
        "чтобы подтвердить запись."
    ),
    "lead_phone_retry": "Не получилось распознать номер. Напишите в формате +7XXXXXXXXXX.",
    "lead_submit_ok": "Спасибо! Администратор свяжется с вами в ближайшее время.",
    "lead_submit_ok_after_hours": (
        "Спасибо за заявку. Клиника сейчас не работает. "
        "Мы свяжемся с вами в рабочее время."
    ),
    "lead_submit_error": "Что-то пошло не так. Проверьте номер и попробуйте ещё раз.",
    "situation_prompt": (
        "Опишите коротко ситуацию — что болит, что беспокоит, или просто какой вопрос. "
        "Врач заранее будет в курсе и это поможет при консультации"
    ),
    "situation_retry_short": (
        "Напишите чуть подробнее — буквально 1–2 фразы. "
        "Чем точнее, тем лучше врач подготовится."
    ),
    "situation_to_lead_name": (
        "Спасибо, записала. Эту информацию передадим в клинику, "
        "чтобы врач заранее понимал вашу ситуацию. Как к вам можно обращаться?"
    ),
    "situation_back_fallback": "Хорошо, продолжим. Задайте вопрос или выберите тему.",
    "lead_offer_declined": "Хорошо. Если появятся вопросы — спрашивайте.",
    "bare_affirmative_fallback": "Напишите, пожалуйста, ваш вопрос — так будет проще подсказать.",
    "followup_choose_topic": "Могу рассказать про этапы или про сроки — что выбрать?",
    "guided_menu_answer": "Могу коротко подсказать и помочь выбрать направление — что для вас важнее?",
    "continuation_clarify_answer": (
        "Могу подсказать по услугам, ценам, врачам или записи. Что вас интересует?"
    ),
}


def resolve_pack_client_id(client_id: str | None) -> str:
    """Map API client_id to client pack directory name."""
    raw = (client_id or "").strip() or DEFAULT_CLIENT_ID
    if raw == "default":
        return "demo"
    return raw


def _pack_path(client_id: str | None, file_name: str) -> str:
    pack = resolve_pack_client_id(client_id)
    return os.path.join(_REPO_ROOT, "clients", pack, file_name)


def _read_yaml(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw if isinstance(raw, dict) else {}


def _cached_load(cache: dict[str, dict[str, Any]], key: str, file_name: str) -> dict[str, Any]:
    with _LOCK:
        if key in cache:
            return cache[key]
    data = _read_yaml(_pack_path(key, file_name))
    with _LOCK:
        cache[key] = data
    return data


def load_features(client_id: str | None) -> dict[str, Any]:
    pack = resolve_pack_client_id(client_id)
    return _cached_load(_FEATURES_CACHE, pack, "features.yaml")


def load_tone_raw(client_id: str | None) -> dict[str, Any]:
    pack = resolve_pack_client_id(client_id)
    return _cached_load(_TONE_CACHE, pack, "tone.yaml")


def load_ui_raw(client_id: str | None) -> dict[str, Any]:
    pack = resolve_pack_client_id(client_id)
    return _cached_load(_UI_CACHE, pack, "ui.yaml")


def load_lead_config(client_id: str | None) -> dict[str, Any]:
    pack = resolve_pack_client_id(client_id)
    return _cached_load(_LEAD_CACHE, pack, "lead_config.yaml")


def load_widget_config(client_id: str | None) -> dict[str, Any]:
    path = _pack_path(client_id, "widget_config.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _nested_get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def tone_to_txt_dict(client_id: str | None) -> dict[str, str]:
    pack = resolve_pack_client_id(client_id)
    with _LOCK:
        if pack in _TXT_CACHE:
            return dict(_TXT_CACHE[pack])
    tone = load_tone_raw(client_id)
    out = dict(_FALLBACK_TXT)
    for path, flat_key in _TONE_KEY_MAP:
        val = _nested_get(tone, path)
        if isinstance(val, str) and val.strip():
            out[flat_key] = val.strip()
    with _LOCK:
        _TXT_CACHE[pack] = dict(out)
    return out


def feature_flag(client_id: str | None, *path: str, default: bool = False) -> bool:
    cur: Any = load_features(client_id)
    for part in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
    if isinstance(cur, bool):
        return cur
    return default


def postgres_events_enabled(client_id: str | None) -> bool:
    feats = load_features(client_id)
    if not feats:
        return True
    pg = feats.get("postgres_events")
    if isinstance(pg, bool):
        return pg
    if isinstance(pg, dict) and "enabled" in pg:
        return bool(pg.get("enabled"))
    return feature_flag(client_id, "postgres_events", "enabled", default=False)


def consult_nudge_enabled(client_id: str | None) -> bool:
    return feature_flag(client_id, "consult_nudge", "enabled", default=True)


def situation_enabled(client_id: str | None) -> bool:
    return feature_flag(client_id, "situation", "enabled", default=True)


def leads_enabled(client_id: str | None) -> bool:
    return feature_flag(client_id, "leads", "enabled", default=False)


def leads_mode(client_id: str | None) -> str:
    feats = load_features(client_id)
    leads = feats.get("leads") if isinstance(feats.get("leads"), dict) else {}
    mode = str((leads or {}).get("mode") or "").strip()
    if mode:
        return mode
    lead_cfg = load_lead_config(client_id)
    return str(lead_cfg.get("delivery") or "demo_stub").strip() or "demo_stub"


def free_consultation_messaging(client_id: str | None) -> bool:
    return feature_flag(client_id, "messaging", "free_consultation", default=True)


@dataclass(frozen=True)
class UiMenu:
    answer: str
    quick_replies: tuple[dict[str, str], ...] = ()
    cta_text: str | None = None
    cta_action: str | None = None


def _parse_quick_replies(raw: Any) -> tuple[dict[str, str], ...]:
    if not isinstance(raw, list):
        return ()
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        ref = str(item.get("ref") or "").strip()
        action = str(item.get("action") or "").strip()
        if ref:
            out.append({"label": label, "ref": ref})
        elif action:
            out.append({"label": label, "action": action})
    return tuple(out)


def _parse_menu(raw: Any, *, default_answer: str) -> UiMenu:
    if not isinstance(raw, dict):
        return UiMenu(answer=default_answer)
    answer = str(raw.get("answer") or default_answer).strip() or default_answer
    cta_text = str(raw.get("cta_text") or "").strip() or None
    cta_action = str(raw.get("cta_action") or "").strip() or None
    return UiMenu(
        answer=answer,
        quick_replies=_parse_quick_replies(raw.get("quick_replies")),
        cta_text=cta_text,
        cta_action=cta_action,
    )


@dataclass(frozen=True)
class UiBundle:
    guided_menu: UiMenu
    continuation_clarify: UiMenu
    low_score: UiMenu
    no_candidates: UiMenu
    offtopic: UiMenu
    empty_question: UiMenu
    bare_affirmative: UiMenu
    consult_nudge_exhausted: str
    consult_nudge_streak: str


_DEFAULT_GUIDED_REPLIES: tuple[dict[str, str], ...] = (
    {"label": "Стоимость имплантации", "ref": "implantation__pricing__implants.md#korotko"},
    {"label": "Больно ли ставить имплант?", "ref": "implantation__faq__pain.md#korotko"},
    {"label": "Что будет на консультации?", "ref": "clinic__info__consultation.md#korotko"},
    {"label": "Хочу записаться", "ref": "lead:booking"},
)

_DEFAULT_CONSULT_EXHAUSTED = (
    "\n\nЗадача на этот ответ:\n"
    "После ответа по вопросу пациенту по этой теме в базе больше нечего добавить — "
    "тема для справочного ответа исчерпана.\n"
    "Заверши ответ естественно: мягко предложи консультацию в клинике "
    "как следующий шаг (своими словами, в том же тоне, без давления).\n"
    "Не предлагай текстом «могу ещё рассказать» — только консультацию, если уместно завершить диалог."
)

_DEFAULT_CONSULT_STREAK = (
    "\n\nЗадача на этот ответ:\n"
    "Пациент уже несколько раз уточнял по теме клиники.\n"
    "Сначала ответь по существу на вопрос, затем в конце того же ответа "
    "мягко предложи консультацию, чтобы разобрать детали лично "
    "(своими словами, без шаблонных фраз и без давления)."
)


def load_ui_bundle(client_id: str | None) -> UiBundle:
    ui = load_ui_raw(client_id)
    fb = ui.get("fallback_menu") if isinstance(ui.get("fallback_menu"), dict) else {}
    guided = ui.get("guided_menu") if isinstance(ui.get("guided_menu"), dict) else {}
    cont = ui.get("continuation_clarify") if isinstance(ui.get("continuation_clarify"), dict) else {}
    cn = ui.get("consult_nudge") if isinstance(ui.get("consult_nudge"), dict) else {}

    guided_menu = _parse_menu(
        guided,
        default_answer=_FALLBACK_TXT["guided_menu_answer"],
    )
    if not guided_menu.quick_replies:
        guided_menu = UiMenu(
            answer=guided_menu.answer,
            quick_replies=_DEFAULT_GUIDED_REPLIES,
            cta_text=guided_menu.cta_text,
            cta_action=guided_menu.cta_action,
        )

    continuation = _parse_menu(
        cont,
        default_answer=_FALLBACK_TXT["continuation_clarify_answer"],
    )
    if not continuation.quick_replies:
        continuation = UiMenu(
            answer=continuation.answer,
            quick_replies=guided_menu.quick_replies,
            cta_text=continuation.cta_text,
            cta_action=continuation.cta_action,
        )

    low_default = (
        "Не нашла точного ответа. Запишитесь на консультацию — администратор свяжется с вами."
    )
    if free_consultation_messaging(client_id):
        low_default = (
            "Не нашла точного ответа. Запишитесь на консультацию, она у нас бесплатная, "
            "цена фиксируется в договоре без скрытых доплат, возможен налоговый вычет 13%."
        )

    return UiBundle(
        guided_menu=guided_menu,
        continuation_clarify=continuation,
        low_score=_parse_menu(fb.get("low_score"), default_answer=low_default),
        no_candidates=_parse_menu(
            fb.get("no_candidates"),
            default_answer=(
                "Не нашла ответа на этот вопрос. Попробуйте спросить иначе — "
                "или запишитесь на консультацию, там разберём."
            ),
        ),
        offtopic=_parse_menu(
            fb.get("offtopic"),
            default_answer=(
                "Я помогаю по вопросам клиники: услуги, цены, подготовка, сроки, запись и контакты. "
                "Если хотите, подскажу по вашему вопросу в этом контексте."
            ),
        ),
        empty_question=_parse_menu(fb.get("empty_question"), default_answer="Уточните вопрос."),
        bare_affirmative=_parse_menu(
            fb.get("bare_affirmative"),
            default_answer=_FALLBACK_TXT["bare_affirmative_fallback"],
        ),
        consult_nudge_exhausted=str(cn.get("exhausted_prompt") or _DEFAULT_CONSULT_EXHAUSTED).strip(),
        consult_nudge_streak=str(cn.get("streak_prompt") or _DEFAULT_CONSULT_STREAK).strip(),
    )


def ui_menu_to_payload(menu: UiMenu, *, sid: str, client_id: str | None, extra_meta: dict | None = None) -> dict:
    from config import default_cta_dict

    meta: dict[str, Any] = {"sid": sid}
    if client_id is not None:
        meta["client_id"] = client_id
    if extra_meta:
        meta.update(extra_meta)
    cta = None
    if menu.cta_text and menu.cta_action:
        cta = {"text": menu.cta_text, "action": menu.cta_action}
    elif menu.cta_action == "lead":
        cta = default_cta_dict()
    quick = [{"label": q["label"], "ref": q.get("ref") or q.get("action") or ""} for q in menu.quick_replies]
    return {
        "answer": menu.answer,
        "quick_replies": quick,
        "cta": cta,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": meta,
    }
