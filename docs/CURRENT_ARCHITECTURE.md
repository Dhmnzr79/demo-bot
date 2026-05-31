# Текущая архитектура бота

**Статус:** фактический runtime (multiclient M1–M4 локально).  
**Целевое / ops:** `MULTICLIENT.md`.  
**Обновлено:** 2026-05.

---

## 0. Multiclient

| Реализовано | Ещё не prod |
|-------------|-------------|
| `clients/{id}/` — md, catalog, prices, policies, tone, features | Контент nikadent / финализация cesi |
| `data/{id}/` — corpus, embeddings, aliases, `bot.db` | VPS deploy (Caddy, wildcard TLS) |
| `core/client_runtime.py`, `client_data_loader.py` | `allowed_origins` — домены сайтов клиник |
| `meta_loader`, `doctors_lookup` → только pack md | Golden evals per `client_id` |
| Host → `client_id` (prod `*.bot.*`) | |
| Origin guard (`core/origin_guard.py`) | |
| Per-client system prompt (`core/llm_system_prompt.py`) | |
| Leads: demo stub / email (`lead_service`, `lead_config.yaml`) | |
| Admin + PG (`admin_dashboard/`, `pg_sink.py`) | |
| Legacy `md/`, `clients/default/`, общий `data/corpus.jsonl` | **удалены** |

API: `client_id` в body/query; alias `default` → pack `demo`. `DEFAULT_CLIENT_ID=demo`.

---

## 1. HTTP-роуты

| Роут | Назначение |
|------|------------|
| `POST /ask` | Основной диалог |
| `POST /ask/stream` | SSE |
| `POST /lead` | Заявка (режим из `features.yaml`) |
| `GET /api/widget-config` | Конфиг embed |
| `GET /dashboard` | JSONL mini-dashboard (prod: 404) |

Debug: `/_debug/ping`, `/__debug/retrieval` — prod: 404 или token.

---

## 2. Пайплайн `/ask`

```
ingress / rate limit → flow_handlers → ref / continuation
→ Resolver (или classify_intent при RESOLVER_OFF=1)
→ contacts overlay → route_source (A3) → retrieval + arbiter
→ chunk_responder → policy → session → JSON
```

Детали маршрутов: `ROUTING_MAP.md`.

---

## 3. Модули

| Модуль | Роль |
|--------|------|
| `app.py` | HTTP, `_orchestrate_ask_turn` |
| `core/client_host.py` | Host → `client_id` (prod) |
| `core/origin_guard.py` | Origin/Referer vs `allowed_origins` |
| `core/startup_check.py` | Старт: артефакты `data/{id}/` |
| `ingress_gate.py` | Noise/offtopic до Resolver |
| `flow_handlers.py` | Lead, situation, booking, «да» |
| `resolver.py` | `DecisionFrame` + safety-net |
| `source_routing.py` | A3: doctor, catalog, price |
| `doctors_lookup.py` | Врачи из `clients/{id}/md/` |
| `query_selector.py` / `retriever.py` | RAG + rerank |
| `arbiter.py` / `content_arbiter.py` | Выбор ref |
| `chunk_responder.py` | Chunk → LLM → policy |
| `session.py` | SQLite `data/{id}/bot.db` |
| `lead_service.py` | Email + PG |
| `pg_sink.py` | Async PG events |
| `admin_dashboard/` | Read-only admin UI |
| `contracts/`, `core/routing.yaml` | Схемы, пороги |

Legacy (не расширять): `llm.classify_intent`, `query_selector.select_catalog_content_route` — см. `DEPRECATED.md`.

---

## 4. Resolver

- Основной путь: `resolver.resolve()` → `DecisionFrame`
- Bypass: env **`RESOLVER_OFF=1`** → `classify_intent`
- Contacts: regex overlay поверх Resolver

---

## 5. Контент и индекс

| Что | Где |
|-----|-----|
| MD | `clients/{id}/md/` |
| Catalog, prices, policies | `clients/{id}/` |
| Индекс | `data/{id}/corpus.jsonl`, `embeddings.npy`, `alias_*` |
| Пересборка | `python build_index.py --client {id\|all}` |

---

## 6. Observability

- JSONL + `emit_bot_event` → optional PG (`BOT_PG_DSN`)
- Боевая админка: `DASHBOARD.md`, `admin.bot.artgents.ru`
- Demo: PG не обязателен (`features.yaml`)

---

## 7. Виджет

Контракт ответа: `WIDGET_ANSWER_FORMAT.md`. Конфиг: `clients/{id}/widget_config.json`.

---

При расхождении док ↔ код: **этот файл + код**; ops/domains — `MULTICLIENT.md`.
