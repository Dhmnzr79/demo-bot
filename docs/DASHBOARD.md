# Дашборд и observability

**Статус:** активный контракт для боевых клиник.  
**Связь:** `MULTICLIENT.md` (M4–M5: PG + `admin_dashboard` для cesi/nikadent; demo — без PG или отдельно).

---

## Когда что нужно

| Режим | Postgres | Admin | Лёгкий `/dashboard` |
|-------|----------|-------|---------------------|
| **demo** (`features.yaml`: postgres off) | не обязателен | не нужен | достаточно для отладки |
| **боевая клиника** | **обязателен** (`BOT_PG_DSN`) | **обязателен** (`admin_dashboard/`) | запасной канал |

JSONL остаётся fallback при сбое PG и для локальной отладки.

---

## 1) Цель

Дашборд отвечает на вопросы:

- Бот сегодня работает нормально?
- Где и почему ошибается?
- Какие вопросы повторяются — доработка базы?
- Сколько лидов?
- Сколько стоит LLM?
- Какие диалоги требуют внимания?

---

## 2) Слои

- **Технический:** `bot_event` + JSONL-логи (`logging_setup.py`, `pg_sink.py`).
- **Продуктовый:** агрегаты в `admin_dashboard/` (диалоги, проблемы, лиды, cost).

---

## 3) Этапы

### Этап 1 — MVP (в коде)

1. События в PostgreSQL + JSONL (`BOT_PG_DSN`).
2. Таблицы: `bot_events`, `leads` (с `client_id`).
3. `turn_complete` с **redacted** полями (не raw PII).
4. `admin_dashboard/`: overview, dialogs, problems, leads, costs, events.

### Этап 2 — позже

Materialized views, `llm_calls`, ротация истории.

---

## 4) Контракт `bot_event`

- `kind = "bot_event"`, `event_type`, `schema_version`, `ts`, `request_id`, `sid`, **`client_id`**, `path`, `status`, `details`.

События: `user_turn_completed`, `bot_reply_completed`, `turn_complete`, `lead_submitted`, `llm_usage`, `llm_error`, `retrieval_selected`, `retrieval_fallback`, `cta_shown`.

---

## 5) `turn_complete`

Обязательные `details`: `turn_number`, `user_text_redacted`, `user_preview_redacted`, `bot_text_redacted`, `intent`, `doc_id`, `route`, `low_score`, `lead_flow`, `handoff_filter`, `answer_chars`, `latency_ms`.

Stream: событие **после** финала ответа, не по дельтам.  
`route` задаётся в одном месте orchestration, не собирается постфактум.

---

## 6) Admin API

Сервис: `admin_dashboard/` (порт `9100`).

- `GET /api/overview`, `/api/dialogs`, `/api/dialogs/<sid>/thread`, `/api/problems`, `/api/leads`, `/api/costs`, `/api/events`
- Фильтр **`?client_id=cesi`** на всех запросах
- `BOT_PG_DSN` обязателен; `ADMIN_DASHBOARD_TOKEN` в prod

Список диалогов — **визиты** внутри browser-сессии (`sid`): новый визит после **заявки** или паузы **>30 мин** (`ADMIN_DIALOG_VISIT_GAP_MIN`). Компактное превью + «Показать диалог» → `GET /api/dialogs/<sid>/thread?visit_index=N`. Метрика «Диалогов» = визиты; «Сессий» = distinct `sid`. Event Explorer — отладка.

---

## 7) Env

| Переменная | Назначение |
|------------|------------|
| `BOT_PG_DSN` | Postgres для bot sink |
| `ADMIN_DASHBOARD_PORT` | default 9100 |
| `ADMIN_DASHBOARD_TOKEN` | prod |

---

## 8) Definition of Done (боевой клиент)

1. `BOT_PG_DSN` задан, события в PG + JSONL.
2. `turn_complete` с redacted текстами.
3. Admin показывает метрики «сегодня» по `client_id`.
4. Диалоги и проблемы видны; лиды после включения `lead_config` (не demo_stub).
5. Demo не смешивается с боевыми в admin (фильтр или `features.admin: false`).

---

## 9) Известное (resolved)

Маскировка `prompt_tokens` как секрета — исправлено в `logging_setup.py` (`_USAGE_TOKEN_KEYS` allowlist).
