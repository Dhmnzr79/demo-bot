# Текущая архитектура бота

**Статус:** снимок **фактического** runtime (до полного multiclient §4.1).  
**Целевое состояние:** `MULTICLIENT.md`.  
**Обновлено:** docs cleanup + multiclient (2026).

---

## 0. Multiclient — что уже есть / чего нет

| Есть в коде | Ещё не сделано (§4.1 MULTICLIENT) |
|-------------|-----------------------------------|
| `client_id` в API, `ALLOWED_CLIENTS` | `clients/{id}/md/` без корневого fallback |
| `clients/default/` catalog, prices | `data/{id}/` corpus/embeddings per client |
| Фильтр corpus по `client_id` в retriever | `client_data_loader` |
| `pg_sink` + `admin_dashboard/` | client-aware `session.py` → `data/{id}/bot.db` |
| | `doctors_lookup` → только `clients/{id}/md/` |
| | Origin check по `widget_config.allowed_origins` |

**Сейчас:** один `DATA_DIR`, один `SQLITE_PATH`, корневой `md/`, `doctors_lookup` читает `md/` — смешение клиник возможно до M1–M2.

---

## 1. Цель версии

- RAG-бот: цены, врачи, контакты, catalog, retrieval.
- Переход к **demo + cesi + nikadent** как изолированным пакетам (`MULTICLIENT.md`).
- `/ask`, `/ask/stream`, `/lead` (demo: lead stub).

---

## 2. HTTP-роуты

| Роут | Назначение |
|------|------------|
| `POST /ask` | Основной диалог |
| `POST /ask/stream` | SSE |
| `POST /lead` | Лид (demo: `demo_stub`) |
| `GET /dashboard` | JSONL mini-dashboard |

Debug: `/_debug/ping`, `/__debug/retrieval` — prod: 404 или token.

---

## 3. Модули

| Модуль | Роль |
|--------|------|
| `app.py` | HTTP, `_orchestrate_ask_turn` |
| `ingress_gate.py` | Noise/offtopic до Resolver |
| `flow_handlers.py` | Lead, situation, booking, «да» |
| `resolver.py` | `DecisionFrame` + safety-net |
| `source_routing.py` | A3: doctor, catalog, price |
| `doctors_lookup.py` | Врачи (**legacy: корневой md/**) |
| `query_selector.py` / `retriever.py` | RAG + rerank |
| `arbiter.py` / `content_arbiter.py` | Выбор ref |
| `chunk_responder.py` | Chunk → LLM → policy |
| `verifier.py` | Shadow/trigger verify |
| `session.py` | SQLite (**один файл на процесс**) |
| `pg_sink.py` | Async PG events |
| `admin_dashboard/` | Read-only admin UI |
| `lead_service.py` | Email + PG (`lead_config.yaml`, `.env` SMTP) |
| `contracts/`, `core/routing.yaml` | Схемы, пороги |

---

## 4. Пайплайн `/ask` (упрощённо)

```
ingress / rate limit → flow_handlers → ref / continuation
→ Resolver (или classify_intent при RESOLVER_OFF=1)
→ contacts overlay → route_source (A3) → retrieval + arbiter
→ chunk_responder → policy → session → JSON
```

Детали: `ROUTING_MAP.md`.

---

## 5. Resolver

- Legacy: `classify_intent` → contacts | price_* | content
- Resolver: `DecisionFrame`; bypass: env **`RESOLVER_OFF=1`**
- Contacts: regex overlay поверх Resolver

---

## 6. Контент (legacy layout)

- MD: **`md/*.md`** (миграция → `clients/{id}/md/`)
- Catalog/prices: **`clients/default/`** (→ per client)
- Индекс: **`data/corpus.jsonl`**, **`data/embeddings.npy`** (→ `data/{id}/`)

---

## 7. Observability

- JSONL + `emit_bot_event` → optional PG (`BOT_PG_DSN`)
- Боевая админка: **`DASHBOARD.md`**, `admin.bot.artgents.ru`
- Demo: PG не обязателен

---

## 8. Виджет

`WIDGET_ANSWER_FORMAT.md`

---

## 9. Намеренно после multiclient M5+

- `guide_router`, `dialog_manager` (ROADMAP Phase 4–5)
- n8n / Redis (ROADMAP Phase 6)

При расхождении док ↔ код: **этот файл + `MULTICLIENT.md` + код**.
