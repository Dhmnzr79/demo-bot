# Карта маршрутизации

**Статус:** Phase 2 — зафиксирована карта (2026-05).  
**Парный документ:** `CURRENT_ARCHITECTURE.md`.  
**Долг / следующие этапы:** `TECH_DEBT.md` → «Routing cleanup».

Цель: один документ «куда уходит вопрос» без чтения всего `app.py`.

---

## Целевой pipeline (куда идём)

```
вопрос
→ guards (ingress, noise, duplicate, anti-spam)
→ flow_handlers (lead, situation, ref, «да» по pending)
→ continuation guards (короткое без контекста / #korotko)
→ Resolver (+ legacy safety-net)
→ contacts overlay (regex, до A3)
→ A3 source_routing (doctor / catalog / price)
→ content retrieval + arbiter
→ chunk_responder → policy → session → JSON
```

**Phase 4 (позже):** после A3 и до retrieval — `guide_router` (только при `features.yaml` → `guide_router.enabled: true`). См. раздел «Roadmap» внизу.

---

## Фактический порядок проверок (`_orchestrate_ask_turn`)

| # | Условие | Orchestration route (`chunk_route` / `service_route`) | Модуль |
|---|---------|---------------------|--------|
| 0 | unknown `client_id` | HTTP 403 | `app.py` |
| 0a | `/reset`, `/новая` | reset session | `session.mem_reset` |
| 0b | rate limit | `rate_limited` | `app.py` |
| 1 | obvious noise (без active lead) | `ingress_obvious_noise` | `app.py` → `ingress_gate` |
| 2 | ingress gate (не skip) | `ingress_*` | `ingress_gate.classify_ingress` |
| 3 | `cta_action`, situation, booking, lead pending | `lead_flow` | `flow_handlers` |
| 4 | active lead resume | `lead_flow` | `flow_handlers.resume_active_lead_flow` |
| 5 | duplicate question | `duplicate_short_circuit` | `app.py` |
| 6 | message burst / soft redirect | `booking_flow` | `app.py` |
| 7 | `ref` в теле | `retrieval_chunk` | `retriever.get_chunk_by_ref` |
| 8 | пустой вопрос | `error` | `app.py` |
| 9 | короткое продолжение без контекста | `continuation_clarify` | `app.py` |
| 10 | `continuation_only_phrase` + `current_doc_id` | `retrieval_chunk` (`#korotko`) | `app.py` |
| 11 | `_is_short_contextual` + `current_doc_id` | `retrieval_chunk` (`#korotko`) | `app.py` |
| 12 | Resolver (или legacy при `RESOLVER_OFF=1`) | задаёт `effective_intent` | `resolver` / `llm` |
| 13 | contacts regex overlay | `contacts_chunk` | `app.py` + `retrieve` + `pick_contacts_chunk` |
| 14 | A3 `route_source` | см. таблицу A3 ниже | `source_routing` |
| 15 | fallback `price_lookup` (если intent) | `price_lookup` | `query_selector.select_price_service_route` |
| 16 | content: Resolver `unknown` + clarify | `guided` | `app.py` |
| 17 | content: candidates + arbiter | `retrieval_chunk` / `catalog_*` / `guided` / fallbacks | `query_selector`, `content_arbiter` |

**Ingress skip:** есть `ref`, active lead или `situation_pending` — ingress gate не вызывается.

---

## A3 `source_routing` → итоговый route

| `SourceRouteResult.source` | Условие | Orchestration route | ref / service_id |
|----------------------------|---------|--------------|------------------|
| `doctor` + cards | ≥2 врача | `doctors_list` | synthetic chunk |
| `doctor` + doc/overview | один ref | `retrieval_chunk` | `doctors__*.md#korotko` |
| `catalog_facts` | content + facts в catalog | `catalog_facts` | `service_id` из catalog |
| `catalog_md` | content + `md_entry_ref` | приоритет в A4/A5 → часто `catalog_md_first` или `retrieval_chunk` | `*.md#korotko` |
| `price_card` / `price_ref` | price match | `price_lookup` | `prices.json` / price ref |
| `price_concern` | concern match | `price_concern` | `concern_ref` (default: `implantation__faq__cost.md#korotko`) |
| `price_lookup_clarify` | услуга не найдена | `price_lookup` | clarify payload |
| `none` | нет match | → ветка 15–17 | — |

---

## Intent → ветка

| Intent / сигнал | Источник | Примечание |
|-----------------|----------|------------|
| contacts | regex overlay в `app.py` | не через Resolver; retrieve full corpus |
| price_lookup | A3 или `select_price_service_route` | цены только из `prices.json` |
| price_concern | A3 concern_ref | |
| doctor | A3 `doctors_lookup` | cards / overview / doc ref |
| catalog facts | A3 `catalog_facts` | facts card без MD |
| catalog md | A3 → A4/A5 | приоритетный ref |
| content | RAG + rerank (+ arbiter) | topic scope опционально (`routing.yaml`) |
| unknown + clarify | Resolver | `guided` menu, не retrieval |

---

## Legacy vs Resolver (Phase 2)

| Область | Основной путь | Legacy / overlay | Когда legacy срабатывает | План Phase 3 |
|---------|---------------|------------------|--------------------------|--------------|
| Intent (price/content) | `resolver.resolve_with_fallback()` → `DecisionFrame.route_intent` | `llm.classify_intent` | `confidence.intent` < порога в `routing.yaml` → safety-net перезаписывает `route_intent` | evals → сузить до edge cases |
| Topic scope | `DecisionFrame.service_topic` | safety-net: topic → `unknown` | `confidence.topic` < порога | оставить guard, не дублировать в app |
| query_mode | `DecisionFrame.query_mode` | safety-net → `specific` | `confidence.query_mode` < порога | влияет на scope guard (comparison/process) |
| Полный bypass | — | `classify_intent` only | `RESOLVER_OFF=1` (+ shadow resolver в логах) | только debug / A/B |
| Contacts | regex `contacts_intent()` в `app.py` | Resolver не должен давать contacts | overlay **после** Resolver, **до** A3 | вынести в `route_guards` (Phase 3) |
| Catalog routing | `source_routing.route_source` (A3) | `query_selector.select_catalog_content_route` | **DEPRECATED**, не вызывается из `/ask` | не расширять |
| Ingress / offtopic | `ingress_gate.classify_ingress` | `llm.classify_handoff_filter` | **DEPRECATED** | не расширять |
| Price match | A3 + `select_price_service_route` | дублирующий fallback в app (ветка 15) | если A3 не вернул price, но `effective_intent=price_lookup` | вынести в `price_flow.py` (Phase 3) |
| Короткое «да» | `pending_lead_offer`, `situation_pending` | — | только lead/situation | Phase 4: `pending_followup_ref` |
| Продолжение темы | `current_doc_id` + `#korotko` | — | нет guide pending | Phase 4: guide clarification slots |

**Правило:** новый код не вызывает DEPRECATED из `DEPRECATED.md`. Legacy safety-net не «чинит» поля LLM эвристиками по ключевым словам запроса — только пороги из `core/routing.yaml`.

---

## Примеры: вопрос → route → ref / service_id

| Вопрос | expected route (smoke) | ref / source | service_id (типично) |
|--------|------------------------|--------------|----------------------|
| Телефон клиники | `contacts_chunk` | `clinic__info__contacts.md` (retrieve pick) | — |
| Хочу записаться | `lead_flow` | flow template | — |
| Сколько стоит имплантация? | `price_lookup` | `prices.json` key | `implantation_classic` (demo) |
| Почему так дорого? | `price_concern` | `implantation__faq__cost.md#korotko` | concern fallback |
| Какие врачи делают имплантацию? | `doctors_list` или `retrieval_chunk` | doctors cards / overview md | — |
| Как проходит имплантация? | `retrieval_chunk` | `implantation__*.md` | — |
| Чем имплантация лучше протезирования? | `retrieval_chunk` (сейчас) | RAG chunk | Resolver: `query_mode=comparison` |
| Какая погода сегодня? | `ingress_hard_stop_non_target` | ingress payload | — |
| «да» после lead offer | `lead_flow` | `pending_lead_offer` | — |
| «короче» при `current_doc_id` | `retrieval_chunk` | `{doc_id}#korotko` | — |

> Сравнительные вопросы (последняя строка с comparison) **сейчас** идут в RAG. Phase 4: при включённом `guide_router` — отдельный route `guide_*`.

---

## Три уровня «route» (не путать)

| Уровень | Где живёт | Назначение |
|---------|-----------|------------|
| **Orchestration route** | `AskOrchestrationResult.chunk_route` / `.service_route` в `app.py`; для chunk-ответов дублируется в **`meta.orch_route`** (`chunk_responder.py`) | внутренняя развилка пайплайна |
| **Smoke route** | `_infer_route_from_response()` в `evals/v5/run_e2e_smoke.py` | контракт `expected_route` в `e2e_smoke.json` — **не** читает `meta.route` |
| **Telemetry route** | PG/JSONL `turn_complete` → `details.route` через `finalize_ask()` / `_infer_route(payload)` | observability, не контракт smoke |

### Как smoke выводит route (`run_e2e_smoke.py`)

Порядок (первое совпадение):

1. `meta.orch_route` ∈ `{price_lookup, doctors_list, contacts_chunk, price_concern}` → как есть
2. `meta.ingress_route` (≠ `normal`) → `ingress_{route}`
3. `meta.handoff_filter` → `handoff_filter`
4. `meta.lead_flow` или `meta.booking_intent` → `lead_flow`
5. `meta.low_score` → `low_score_fallback`
6. `meta.error == rate_limited` → `rate_limited`
7. `meta.intent` ∈ `{price_lookup, price_concern, offtopic, catalog_facts}` → как intent
8. `meta.file == clinic__info__contacts.md` → `contacts_chunk`
9. `__pricing__` в `meta.file` → `price_lookup`
10. любой другой непустой `meta.file` → `retrieval_chunk`
11. непустые `quick_replies` → `guided`
12. иначе → `""` (FAIL, если в кейсе задан `expected_route`)

**Важно:** многие orchestration-маршруты из `app.py` smoke **не различает** и сводит к более грубым меткам. Примеры:

| Orchestration (`service_route` / `chunk_route`) | Что увидит smoke |
|-------------------------------------------------|------------------|
| `catalog_md_first` | `retrieval_chunk` (есть `meta.file`) |
| `retrieval_no_candidates` | часто `guided` (quick_replies) или `""` |
| `continuation_clarify`, `duplicate_short_circuit`, `booking_flow` | **нет** стабильного контракта — не использовать в smoke без доработки runner (Phase 3) |
| chunk с `orch_route=retrieval_chunk` | `retrieval_chunk` (шаг 10) |

---

## Значения smoke route (`expected_route`)

Используются в `evals/v5/e2e_smoke.json` — сравниваются с результатом `_infer_route_from_response()`, **не** с полем `meta.route` (его в JSON ответа `/ask` нет).

| Smoke route | Как распознаётся | Примеры case id |
|-------------|------------------|-----------------|
| `contacts_chunk` | `orch_route` или `meta.file=clinic__info__contacts.md` | `smoke_contacts_phone` |
| `lead_flow` | `meta.lead_flow` / `meta.booking_intent` | `smoke_booking_want` |
| `price_lookup` | `orch_route`, `meta.intent`, или `__pricing__` в file | `smoke_price_classic` |
| `price_concern` | `orch_route` или `meta.intent` | `smoke_price_concern_expensive` |
| `retrieval_chunk` | `meta.file` (content md) | `smoke_content_impl_process_with_doctor_word` |
| `doctors_list` | `meta.orch_route=doctors_list` | `smoke_doctors_who_classic_implant` (`expected_route_any`) |
| `catalog_facts` | `meta.intent=catalog_facts` | *(пока нет отдельного smoke-кейса)* |
| `guided` | `quick_replies` без file | `smoke_noise_unclear_short` |
| `ingress_*` | `meta.ingress_route` | `smoke_handoff_weather` → `ingress_hard_stop_non_target` |
| `low_score_fallback` | `meta.low_score` | *(пока нет отдельного smoke-кейса)* |

Runner: `python evals/v5/run_e2e_smoke.py` (см. `evals/v5/README.md`).

**Phase 3 (долг):** расширить runner (`orch_route` для всех chunk_route, явные service_route) или добавить `meta.smoke_route` — см. `TECH_DEBT.md`.

---

## Evals — привязка к маршрутам

| Файл | Что проверяет | Запуск |
|------|---------------|--------|
| `evals/v5/e2e_smoke.json` | end-to-end `/ask`, inferred smoke route, must_contain | `python evals/v5/run_e2e_smoke.py` |
| `evals/v5/resolver_golden.json` | `DecisionFrame` (intent, topic, query_mode) | `python evals/v5/run_layer_eval.py --layer resolver` |
| `evals/v5/arbiter_golden.json` | выбор ref при 2+ кандидатах | `--layer arbiter` |
| `evals/v5/ingress_golden.json` | ingress gate | `--layer ingress` |
| `evals/v5/gate_golden.json` | gate layer | `--layer gate` |

**Smoke ↔ route (выборка — id из `e2e_smoke.json`):**

| case id | expected_route |
|---------|----------------|
| `smoke_contacts_phone` | `contacts_chunk` |
| `smoke_booking_want` | `lead_flow` |
| `smoke_price_classic` | `price_lookup` |
| `smoke_price_concern_general_no_service` | `price_concern` |
| `smoke_content_impl_process_with_doctor_word` | `retrieval_chunk` |
| `smoke_doctors_who_classic_implant` | `doctors_list` \| `retrieval_chunk` (`expected_route_any`) |
| `smoke_cross_topic_ortho_comparison` | `retrieval_chunk` |
| `smoke_handoff_weather` | `ingress_hard_stop_non_target` |
| `smoke_noise_unclear_short` | `guided` |
| `smoke_ingress_pediatric` | `ingress_service_not_offered` |

Baseline smoke: **35** PASS (фиксирован в `e2e_smoke.json`). Known failures — массив `known_v4_failures` в том же файле.

---

## Env / флаги

| Переменная | Эффект |
|------------|--------|
| `RESOLVER_OFF=1` | Только `classify_intent`; Resolver в shadow (`V5_RESOLVER_SHADOW_ON`) |
| `V5_RESOLVER_SHADOW_ON` | fire-and-forget shadow Resolver при bypass |
| `MODEL_RESOLVER` | модель Resolver (default `gpt-5.4-nano`) |
| Пороги confidence | `core/routing.yaml` → `THRESHOLDS` |

Per-client: `clients/{id}/features.yaml` — `guide_router.enabled` (Phase 4, сейчас `false` везде).

---

## Roadmap routing cleanup

| Phase | Задача | Статус |
|-------|--------|--------|
| **2** | Карта маршрутов (этот документ): legacy vs Resolver, примеры, evals | **done** |
| **3** | Smoke расширение; вынос оркестрации из `app.py` (`orchestration/`); legacy cleanup по таблице выше | next |
| **4** | `pending_followup_ref` / clarification slots; первый `guide_router` + golden | после Phase 3 |

**Не делать в одном PR:** вынос `app.py` + смена routing + guide_router.

**Не добавлять guide_router в pipeline до Phase 4** — отдельная ветка после hard routes и стабильного smoke.
